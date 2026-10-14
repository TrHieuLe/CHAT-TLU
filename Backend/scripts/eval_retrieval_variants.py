"""
eval_retrieval_variants.py — So sánh các cách gộp (fusion) dense + sparse trên Qdrant thật.

Bước 1: với mỗi câu hỏi của bộ test TLU, embed (BGE-M3) và lấy RIÊNG danh sách dense top-N,
        sparse top-N và kết quả RRF hiện tại của Qdrant; lưu cache JSON (chỉ chạy lại khi --refresh).
Bước 2: tính offline các biến thể fusion trên cùng dữ liệu, đo Hit@K / MRR@K / Hit@2K
        theo ground_truth (so khớp tên file).

Khác benchmark_eval/scripts/eval_table_4_1_retrieval.py (mô phỏng TF-IDF, không dùng Qdrant):
script này đo đúng index và model mà chatbot đang dùng.

Cách dùng (trong thư mục Backend/):
    python -X utf8 scripts/eval_retrieval_variants.py            # toàn bộ bộ test
    python -X utf8 scripts/eval_retrieval_variants.py --refresh  # lấy lại dữ liệu từ Qdrant
    python -X utf8 scripts/eval_retrieval_variants.py --testset ../benchmark_eval/data/tlu_testset_clean.json

Mỗi bộ test có cache riêng; ground_truth luôn đọc lại từ file bộ test nên sửa nhãn không cần --refresh.
"""
import argparse
import asyncio
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.rag.query_enhancer import enhance_query  # noqa: E402

TESTSET = ROOT.parent / "benchmark_eval" / "data" / "tlu_testset_246.json"
CACHE_DIR = ROOT / "scripts" / ".cache"


def cache_path(testset: Path) -> Path:
    # Giữ tên cache cũ cho bộ mặc định để không phải gọi lại Qdrant
    if testset.resolve() == TESTSET.resolve():
        return CACHE_DIR / "retrieval_lists.json"
    return CACHE_DIR / f"retrieval_lists_{testset.stem}.json"


def basename(name: str) -> str:
    return (name or "").replace("\\", "/").split("/")[-1]


async def fetch_lists(questions: list[dict], depth: int) -> list[dict]:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.http import models
    from app.rag import embedder

    client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY, timeout=60)
    col = settings.QDRANT_COLLECTION
    raw = [q["question"] for q in questions]
    enh = [enhance_query(q) for q in raw]
    texts = list(dict.fromkeys(raw + enh))
    print(f"Embed {len(texts)} câu truy vấn...", flush=True)
    dense, sparse = embedder.get_embeddings(texts, max_length=settings.QUERY_MAX_LENGTH)
    emb = {t: (d.tolist(), s) for t, d, s in zip(texts, dense, sparse)}

    def pts(res):
        return [{"id": str(p.id), "doc": basename(p.payload.get("doc_name", "")), "score": p.score} for p in res.points]

    async def lists_for(text: str) -> dict:
        d, s = emb[text]
        sv = models.SparseVector(indices=[int(i) for i in s], values=[float(v) for v in s.values()])
        rd = await client.query_points(col, query=d, using="dense", limit=depth, with_payload=["doc_name"])
        rs = await client.query_points(col, query=sv, using="sparse", limit=depth, with_payload=["doc_name"])
        rr = await client.query_points(
            col,
            prefetch=[models.Prefetch(query=d, using="dense", limit=100),
                      models.Prefetch(query=sv, using="sparse", limit=100)],
            query=models.FusionQuery(fusion=models.Fusion.RRF), limit=depth, with_payload=["doc_name"],
        )
        return {"dense": pts(rd), "sparse": pts(rs), "qdrant_rrf": pts(rr)}

    by_text = {}
    for i, t in enumerate(texts, 1):
        by_text[t] = await lists_for(t)
        if i % 50 == 0:
            print(f"  {i}/{len(texts)}", flush=True)
    out = []
    for q, r, e in zip(questions, raw, enh):
        out.append({
            "id": q.get("id"), "question": r, "enhanced": e,
            "ground_truth": [basename(g) for g in q["ground_truth"]],
            "raw_lists": by_text[r], "enh_lists": by_text[e],
        })
    return out


# ─── Fusion offline ──────────────────────────────────────────────────────────

def rrf(lists: list[list[dict]], weights: list[float], k: int) -> list[dict]:
    scores, info = {}, {}
    for lst, w in zip(lists, weights):
        for rank, p in enumerate(lst):
            scores[p["id"]] = scores.get(p["id"], 0.0) + w / (k + rank + 1)
            info[p["id"]] = p
    return [info[i] for i in sorted(scores, key=scores.get, reverse=True)]


def score_fusion(lists: list[list[dict]], weights: list[float]) -> list[dict]:
    """Chuẩn hóa min-max điểm từng danh sách rồi cộng có trọng số (giống ý tưởng DBSF)."""
    scores, info = {}, {}
    for lst, w in zip(lists, weights):
        if not lst:
            continue
        vals = [p["score"] for p in lst]
        lo, hi = min(vals), max(vals)
        for p in lst:
            norm = (p["score"] - lo) / (hi - lo) if hi > lo else 1.0
            scores[p["id"]] = scores.get(p["id"], 0.0) + w * norm
            info[p["id"]] = p
    return [info[i] for i in sorted(scores, key=scores.get, reverse=True)]


def metrics(ranked: list[list[dict]], items: list[dict], k: int) -> dict:
    hit, hit2, rr = 0, 0, []
    for docs, it in zip(ranked, items):
        gt = set(it["ground_truth"])
        names = [p["doc"] for p in docs]
        hit += any(d in gt for d in names[:k])
        hit2 += any(d in gt for d in names[:2 * k])
        rank = next((i + 1 for i, d in enumerate(names[:k]) if d in gt), None)
        rr.append(1 / rank if rank else 0)
    n = len(items)
    return {"hit@k": hit / n, "mrr@k": statistics.mean(rr), "hit@2k": hit2 / n}


def variants(it: dict) -> dict:
    """Mỗi biến thể trả về danh sách chunk đã xếp hạng cho một câu hỏi."""
    e, r = it["enh_lists"], it["raw_lists"]
    v = {
        "qdrant_rrf (hiện tại)": e["qdrant_rrf"],
        "dense": e["dense"],
        "sparse": e["sparse"],
        "qdrant_rrf câu gốc (không enhancer)": r["qdrant_rrf"],
    }
    for k in (2, 10, 60):
        v[f"rrf k={k}"] = rrf([e["dense"], e["sparse"]], [1, 1], k)
    for ws in (0.5, 1.5, 2.0, 3.0):
        v[f"rrf k=60 w_sparse={ws}"] = rrf([e["dense"], e["sparse"]], [1, ws], 60)
    for a in (0.3, 0.5, 0.7):
        v[f"score_fusion dense={a}"] = score_fusion([e["dense"], e["sparse"]], [a, 1 - a])
    v["rrf k=60 4 danh sách (gốc + enhancer)"] = rrf(
        [e["dense"], e["sparse"], r["dense"], r["sparse"]], [1, 1, 1, 1], 60
    )
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth", type=int, default=50, help="số kết quả lấy cho mỗi danh sách")
    ap.add_argument("--k", type=int, default=settings.TOP_K)
    ap.add_argument("--testset", type=Path, default=TESTSET, help="file JSON bộ test (id, question, ground_truth)")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--out", type=Path, default=None, help="ghi bảng kết quả ra file markdown")
    args = ap.parse_args()

    data = json.loads(args.testset.read_text(encoding="utf-8"))
    cache = cache_path(args.testset)
    items = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() and not args.refresh else None
    if items is None or [it["question"] for it in items] != [q["question"] for q in data]:
        items = asyncio.run(fetch_lists(data, args.depth))
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    for it, q in zip(items, data):
        it["ground_truth"] = [basename(g) for g in q["ground_truth"]]

    per_variant: dict[str, list] = {}
    for it in items:
        for name, ranked in variants(it).items():
            per_variant.setdefault(name, []).append(ranked)

    k = args.k
    lines = [
        f"{len(items)} câu hỏi (`{args.testset.name}`), collection `{settings.QDRANT_COLLECTION}`, K={k}",
        "",
        f"| Biến thể | Hit@{k} | MRR@{k} | Hit@{2 * k} |",
        "|---|---|---|---|",
    ]
    for name, ranked in per_variant.items():
        m = metrics(ranked, items, k)
        lines.append(f"| {name} | {m['hit@k']:.1%} | {m['mrr@k']:.3f} | {m['hit@2k']:.1%} |")
    report = "\n".join(lines)
    print(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
