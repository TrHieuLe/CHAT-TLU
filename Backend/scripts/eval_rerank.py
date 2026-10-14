"""
eval_rerank.py — So sánh tốc độ / chất lượng các cấu hình reranker trên bộ test TLU.

Bước 1: lấy ứng viên (hybrid RRF) từ Qdrant MỘT lần cho mỗi câu hỏi, lưu cache JSON.
Bước 2: chạy từng biến thể reranker trên cùng tập ứng viên, đo:
  - Hit@K / MRR theo ground_truth (so khớp tên file, bỏ thư mục)
  - overlap@K với cấu hình gốc (fp32, max_length=512)
  - thời gian rerank p50/p95 mỗi câu

Cách dùng:
    python scripts/eval_rerank.py --n 40
    python scripts/eval_rerank.py --n 40 --variants rrf,fp32_512,int8_512
"""
import argparse
import asyncio
import json
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.rag.query_enhancer import enhance_query  # noqa: E402

TESTSET = ROOT.parent / "benchmark_eval" / "data" / "tlu_testset_246.json"
CACHE = ROOT / "scripts" / ".cache" / "rerank_candidates.json"
TOP_K = settings.TOP_K


def basename(name: str) -> str:
    return (name or "").replace("\\", "/").split("/")[-1]


async def build_candidates(questions: list[dict], k: int) -> list[dict]:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.http import models
    from app.rag import embedder

    client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY, timeout=60)
    queries = [enhance_query(q["question"]) for q in questions]
    dense, sparse = embedder.get_embeddings(queries, max_length=settings.QUERY_MAX_LENGTH)
    out = []
    for q, query, d, s in zip(questions, queries, dense, sparse):
        prefetch = [models.Prefetch(query=d.tolist(), using="dense", limit=100)]
        if s:
            prefetch.append(models.Prefetch(
                query=models.SparseVector(indices=[int(i) for i in s], values=[float(v) for v in s.values()]),
                using="sparse", limit=100,
            ))
        res = await client.query_points(
            collection_name=settings.QDRANT_COLLECTION, prefetch=prefetch,
            query=models.FusionQuery(fusion=models.Fusion.RRF), with_payload=True, limit=k,
        )
        out.append({
            "id": q["id"], "question": q["question"], "query": query,
            "ground_truth": [basename(g) for g in q["ground_truth"]],
            "candidates": [{"doc_name": p.payload.get("doc_name", ""), "content": p.payload.get("content", ""),
                            "rrf": p.score} for p in res.points],
        })
    return out


def load_reranker(quantize: bool):
    import torch
    from FlagEmbedding import FlagReranker
    m = FlagReranker(settings.RERANKER_MODEL, use_fp16=False)
    if quantize:
        m.model = torch.ao.quantization.quantize_dynamic(m.model, {torch.nn.Linear}, dtype=torch.qint8)
    m.compute_score([["khởi động", "khởi động"]])
    return m


def metrics(order_docs: list[list[str]], items: list[dict]) -> dict:
    hits, rr = 0, []
    for docs, it in zip(order_docs, items):
        gt = set(it["ground_truth"])
        top = [basename(d) for d in docs[:TOP_K]]
        hits += any(d in gt for d in top)
        rank = next((i + 1 for i, d in enumerate(top) if d in gt), None)
        rr.append(1 / rank if rank else 0)
    return {"hit@k": round(hits / len(items), 3), "mrr": round(statistics.mean(rr), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--k", type=int, default=settings.RETRIEVE_CANDIDATES_K, help="số ứng viên lấy từ Qdrant")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--refresh", action="store_true", help="lấy lại ứng viên từ Qdrant")
    ap.add_argument("--variants", default="rrf,fp32_512,fp32_256,int8_512,int8_256")
    args = ap.parse_args()

    import torch, os
    torch.set_num_threads(settings.TORCH_NUM_THREADS or os.cpu_count() or 1)

    if CACHE.exists() and not args.refresh:
        items = json.loads(CACHE.read_text(encoding="utf-8"))
    else:
        data = json.loads(TESTSET.read_text(encoding="utf-8"))
        random.Random(args.seed).shuffle(data)
        print(f"Lấy ứng viên cho {args.n} câu hỏi từ Qdrant...")
        items = asyncio.run(build_candidates(data[:args.n], args.k))
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    items = [it for it in items if it["candidates"]][:args.n]
    print(f"{len(items)} câu hỏi, {args.k} ứng viên/câu, top_k={TOP_K}\n")

    results, baseline_top = {}, None
    models_cache = {}
    for variant in args.variants.split(","):
        orders, times = [], []
        if variant == "rrf":
            orders = [[c["doc_name"] for c in it["candidates"]] for it in items]
            idx_orders = [list(range(len(it["candidates"]))) for it in items]
        else:
            quant, max_len = variant.split("_")
            key = quant == "int8"
            if key not in models_cache:
                models_cache[key] = load_reranker(quantize=key)
            model = models_cache[key]
            idx_orders = []
            for it in items:
                pairs = [[it["query"], c["content"]] for c in it["candidates"]]
                t0 = time.perf_counter()
                scores = model.compute_score(pairs, batch_size=settings.RERANKER_BATCH_SIZE, max_length=int(max_len))
                times.append((time.perf_counter() - t0) * 1000)
                scores = scores if isinstance(scores, list) else [scores]
                idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
                idx_orders.append(idx)
                orders.append([it["candidates"][i]["doc_name"] for i in idx])
        m = metrics(orders, items)
        tops = [set(o[:TOP_K]) for o in idx_orders]
        if variant == "fp32_512":
            baseline_top = tops
        m["time_p50_ms"] = round(statistics.median(times), 0) if times else 0
        m["time_p95_ms"] = round(sorted(times)[int(0.95 * (len(times) - 1))], 0) if times else 0
        results[variant] = (m, tops)
        print(f"{variant:<10} {m}", flush=True)

    if baseline_top:
        print("\noverlap top-k với fp32_512 (1.0 = chọn đúng y hệt các chunk):")
        for variant, (_, tops) in results.items():
            ov = statistics.mean(len(a & b) / max(len(b), 1) for a, b in zip(tops, baseline_top))
            print(f"  {variant:<10} {ov:.3f}")


if __name__ == "__main__":
    main()
