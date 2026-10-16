"""
eval_answers.py — Đo chất lượng CÂU TRẢ LỜI cuối cùng của chatbot trên Qdrant + Gemini thật.

Hai cấu hình được đo trên cùng bộ câu hỏi:
  studybot : pipeline thật của route chat (build_rag_prompt → SYSTEM_INSTRUCTION → Gemini → postprocess)
  no_rag   : cùng model, system prompt trung tính, KHÔNG đưa ngữ cảnh (baseline "LLM thuần")

Các bước (đều có cache trong scripts/.cache/, chạy lại sẽ tiếp tục chỗ dở — tiện khi gặp 429):
  1. generate : sinh câu trả lời cho từng câu × cấu hình
  2. judge    : một model Gemini mạnh hơn chấm từng câu trả lời theo ngữ cảnh StudyBot truy xuất được
                (claims supported/unsupported, answer relevance, context đủ hay không, từ chối, key facts)
  3. report   : tổng hợp + khoảng tin cậy 95% bootstrap → benchmark_eval/results/answer_eval_<testset>.{json,md}

Hiệu chỉnh judge: --export-calibration ghi CSV 30 mẫu để chấm tay; --calibrate đọc lại CSV đã chấm
và tính % đồng thuận + Cohen's kappa giữa judge và người chấm.

Cách dùng (trong thư mục Backend/, cần Qdrant chạy và GEMINI_API_KEY):
    python -X utf8 scripts/eval_answers.py --n 10                 # chạy thử 10 câu đầu
    python -X utf8 scripts/eval_answers.py                        # toàn bộ bộ test
    python -X utf8 scripts/eval_answers.py --export-calibration   # xuất CSV chấm tay
    python -X utf8 scripts/eval_answers.py --calibrate            # so judge với nhãn chấm tay
"""
import argparse
import asyncio
import csv
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.eval.answer_metrics import (  # noqa: E402
    JUDGE_SCHEMA, aggregate, agreement, build_judge_prompt, cohen_kappa, item_scores, parse_judgment,
)

TESTSET = ROOT.parent / "benchmark_eval" / "data" / "tlu_answer_eval.json"
CACHE_DIR = ROOT / "scripts" / ".cache"
RESULTS_DIR = ROOT.parent / "benchmark_eval" / "results"
CONFIGS = ("studybot", "no_rag")
DEFAULT_JUDGE = "gemini-flash-latest"
# Baseline LLM thuần: KHÔNG dùng SYSTEM_INSTRUCTION của StudyBot — prompt đó bắt từ chối khi thiếu ngữ cảnh
# nên không có ngữ cảnh thì model từ chối 100%, không đo được gì. Prompt trung tính để model tự trả lời.
NO_RAG_SYSTEM = "Bạn là trợ lý học vụ cho sinh viên Trường Đại học Thủy Lợi (TLU). Trả lời câu hỏi bằng tiếng Việt."

METRIC_LABELS = [
    ("faithfulness", "Faithfulness (khẳng định có căn cứ trong tài liệu)"),
    ("answer_relevance", "Answer Relevance (đúng trọng tâm)"),
    ("context_relevance", "Context Relevance (ngữ cảnh đủ để trả lời)"),
    ("correctness", "Correctness (tỷ lệ ý bắt buộc nêu đúng)"),
    ("contradiction_rate", "Tỷ lệ câu nêu SAI ý bắt buộc"),
    ("refusal_recall", "Từ chối đúng khi tài liệu không có"),
    ("false_refusal_rate", "Từ chối sai khi tài liệu có"),
    ("citation_rate", "Tỷ lệ có trích dẫn Điều/Khoản"),
    ("wrong_citation_rate", "Tỷ lệ trích dẫn Điều không có trong tài liệu"),
]


# ─── Cache JSONL ─────────────────────────────────────────────────────────────

def load_jsonl(path: Path) -> dict:
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                out[(rec["id"], rec["config"])] = rec
    return out


def append_jsonl(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


class RateLimiter:
    def __init__(self, rpm: float):
        self.interval = 60.0 / rpm if rpm > 0 else 0.0
        self._last = 0.0

    async def wait(self):
        delay = self._last + self.interval - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
        self._last = time.monotonic()


def _is_transient(err: str) -> bool:
    e = err.lower()
    return any(k in e for k in ("429", "503", "quota", "resource_exhausted", "unavailable", "overloaded", "timeout"))


# ─── 1. Generate ─────────────────────────────────────────────────────────────

async def generate_one(item: dict, config: str) -> dict:
    from app.llm.llm_service import llm_service
    from app.routers.chat import SYSTEM_INSTRUCTION, build_rag_prompt, postprocess_answer

    t0 = time.perf_counter()
    # Mỗi câu hỏi đứng độc lập (bộ test đã bỏ câu nối tiếp) → không có history, không cần resolve_question
    rag = await build_rag_prompt(item["question"], retrieve=True)
    if config == "studybot":
        prompt, system = rag.prompt, SYSTEM_INSTRUCTION
    else:
        prompt, system = item["question"], NO_RAG_SYSTEM
    t_ret = time.perf_counter()

    full = ""
    async for delta in llm_service.stream_chat_response(history=[], prompt=prompt, system_instruction=system):
        full += delta or ""
    if not full.strip():
        raise RuntimeError("LLM không trả về nội dung (có thể do 429/503)")
    answer = postprocess_answer(full, item["question"])

    return {
        "id": item["id"], "config": config, "question": item["question"], "answer": answer,
        # Luôn lưu ngữ cảnh StudyBot truy xuất được: là ngữ cảnh thật (studybot) hoặc bằng chứng tham chiếu (no_rag)
        "ctx_parts": rag.ctx_parts, "source_names": rag.source_names,
        "retrieval_ms": round((t_ret - t0) * 1000), "total_ms": round((time.perf_counter() - t0) * 1000),
    }


async def run_generate(items: list[dict], path: Path, limiter: RateLimiter, retries: int) -> dict:
    done = load_jsonl(path)
    todo = [(it, c) for it in items for c in CONFIGS if (it["id"], c) not in done]
    print(f"[generate] đã có {len(done)}, cần sinh {len(todo)}", flush=True)
    for k, (it, cfg) in enumerate(todo, 1):
        for attempt in range(retries + 1):
            await limiter.wait()
            try:
                rec = await generate_one(it, cfg)
                append_jsonl(path, rec)
                done[(it["id"], cfg)] = rec
                break
            except Exception as e:  # noqa: BLE001
                wait = min(120, 10 * 2 ** attempt)
                if attempt < retries and (_is_transient(str(e)) or "không trả về" in str(e)):
                    print(f"  ! id={it['id']} {cfg}: {str(e)[:100]} → thử lại sau {wait}s", flush=True)
                    await asyncio.sleep(wait)
                else:
                    print(f"  ✗ id={it['id']} {cfg}: {str(e)[:160]} — bỏ qua, chạy lại để thử tiếp", flush=True)
                    break
        if k % 10 == 0:
            print(f"  {k}/{len(todo)}", flush=True)
    return done


# ─── 2. Judge ────────────────────────────────────────────────────────────────

async def judge_one(client, model: str, item: dict, ans: dict, reference_ctx: list[str]) -> dict:
    from google.genai import types

    prompt = build_judge_prompt(item["question"], reference_ctx, ans["answer"], item.get("key_facts"))
    res = await client.aio.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=JUDGE_SCHEMA,
        ),
    )
    raw = getattr(res, "text", None) or ""
    parsed = parse_judgment(raw)
    if parsed is None:
        raise ValueError(f"judge trả JSON không hợp lệ: {raw[:120]}")
    return {"id": item["id"], "config": ans["config"], "judge_model": model, **parsed}


async def run_judge(items: list[dict], answers: dict, path: Path, model: str,
                    limiter: RateLimiter, retries: int) -> dict:
    from app.llm.llm_service import llm_service

    client = llm_service._get_client()
    if client is None:
        sys.exit("Chưa cấu hình GEMINI_API_KEY / GOOGLE_API_KEY")
    done = load_jsonl(path)
    todo = [(it, c) for it in items for c in CONFIGS
            if (it["id"], c) in answers and (it["id"], c) not in done]
    print(f"[judge:{model}] đã có {len(done)}, cần chấm {len(todo)}", flush=True)
    for k, (it, cfg) in enumerate(todo, 1):
        ref = (answers.get((it["id"], "studybot")) or {}).get("ctx_parts") or []
        for attempt in range(retries + 1):
            await limiter.wait()
            try:
                rec = await judge_one(client, model, it, answers[(it["id"], cfg)], ref)
                append_jsonl(path, rec)
                done[(it["id"], cfg)] = rec
                break
            except Exception as e:  # noqa: BLE001
                wait = min(120, 10 * 2 ** attempt)
                if attempt < retries:
                    print(f"  ! id={it['id']} {cfg}: {str(e)[:100]} → thử lại sau {wait}s", flush=True)
                    await asyncio.sleep(wait)
                else:
                    print(f"  ✗ id={it['id']} {cfg}: {str(e)[:160]} — bỏ qua", flush=True)
        if k % 10 == 0:
            print(f"  {k}/{len(todo)}", flush=True)
    return done


# ─── 3. Report ───────────────────────────────────────────────────────────────

def score_rows(items: list[dict], answers: dict, judgments: dict, config: str) -> list[dict]:
    rows = []
    for it in items:
        ans = answers.get((it["id"], config))
        if ans is None:
            continue
        ref = (answers.get((it["id"], "studybot")) or {}).get("ctx_parts") or []
        j = judgments.get((it["id"], config))
        rows.append({"item": it, "answer": ans, "judgment": j, "scores": item_scores(it, ans, j, ref)})
    return rows


def _fmt(m: dict, pct: bool) -> str:
    if not m or m["mean"] is None:
        return "N/A"
    if pct:
        return f"{m['mean'] * 100:.1f}% [{m['ci'][0] * 100:.0f}–{m['ci'][1] * 100:.0f}] (n={m['n']})"
    return f"{m['mean']:.2f} [{m['ci'][0]:.2f}–{m['ci'][1]:.2f}] (n={m['n']})"


PCT_METRICS = {"contradiction_rate", "refusal_recall", "false_refusal_rate", "citation_rate", "wrong_citation_rate"}


def render_table(summary: dict) -> str:
    lines = [
        "| Chỉ số | LLM thuần (không RAG) | StudyBot |",
        "|---|---|---|",
    ]
    for key, label in METRIC_LABELS:
        pct = key in PCT_METRICS
        nr = "N/A" if key == "context_relevance" else _fmt(summary["no_rag"].get(key), pct)
        lines.append(f"| {label} | {nr} | {_fmt(summary['studybot'].get(key), pct)} |")
    return "\n".join(lines)


def write_report(items, answers, judgments, testset: Path, judge_model: str) -> Path:
    per_config = {c: score_rows(items, answers, judgments, c) for c in CONFIGS}
    summary = {c: aggregate(rows) for c, rows in per_config.items()}
    missing_j = sum(1 for c in CONFIGS for r in per_config[c] if r["judgment"] is None)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_json = RESULTS_DIR / f"answer_eval_{testset.stem}.json"
    meta = {
        "testset": testset.name, "n_items": len(items), "judge_model": judge_model,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "missing_judgments": missing_j,
    }
    try:
        from app.core.config import settings
        meta |= {"answer_model": settings.GEMINI_MODEL, "temperature": settings.TEMPERATURE,
                 "retrieve_k": settings.RETRIEVE_CANDIDATES_K, "reranker": settings.ENABLE_RERANKER}
    except Exception:  # noqa: BLE001
        pass
    details = {c: [{"id": r["item"]["id"], "question": r["item"]["question"],
                    "expect_refusal": bool(r["item"].get("expect_refusal")),
                    "answer": r["answer"]["answer"], "source_names": r["answer"].get("source_names"),
                    "judgment": r["judgment"], "scores": r["scores"]} for r in rows]
               for c, rows in per_config.items()}
    out_json.write_text(json.dumps({"meta": meta, "summary": summary, "details": details},
                                   ensure_ascii=False, indent=1), encoding="utf-8")

    # Các câu StudyBot làm kém nhất để đọc tay
    worst = sorted(
        (r for r in per_config["studybot"] if not r["item"].get("expect_refusal")),
        key=lambda r: (r["scores"]["faithfulness"] if r["scores"]["faithfulness"] is not None else 1.0,
                       r["scores"]["answer_relevance"] if r["scores"]["answer_relevance"] is not None else 1.0),
    )[:10]
    md = [
        f"# Đánh giá chất lượng câu trả lời — `{testset.name}`",
        "",
        f"*Sinh lúc {meta['generated_at']} · {len(items)} câu · model trả lời `{meta.get('answer_model')}`"
        f" · judge `{judge_model}` · thiếu {missing_j} lượt chấm*",
        "",
        "Số trong ngoặc vuông là khoảng tin cậy 95% (bootstrap); n là số câu tính chỉ số đó.",
        "Faithfulness của cột LLM thuần được chấm theo cùng ngữ cảnh StudyBot truy xuất được (bằng chứng tham chiếu).",
        "",
        render_table(summary),
        "",
        "## 10 câu StudyBot điểm thấp nhất",
        "",
    ]
    for r in worst:
        s = r["scores"]
        f = "N/A" if s["faithfulness"] is None else f"{s['faithfulness']:.2f}"
        a = "N/A" if s["answer_relevance"] is None else f"{s['answer_relevance']:.2f}"
        md.append(f"- **id {r['item']['id']}** — {r['item']['question']} · faith={f} · rel={a}"
                  f" · refused={s['refused']} · ctx_đủ={s['context_sufficient']}")
    out_md = out_json.with_suffix(".md")
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    print("\n" + render_table(summary))
    print(f"\nĐã ghi {out_json}\n       {out_md}")
    return out_json


# ─── Hiệu chỉnh judge ────────────────────────────────────────────────────────

CALIB_FIELDS = ["id", "config", "question", "context", "answer",
                "judge_faithful", "judge_refused", "human_faithful", "human_refused", "note"]


def calibration_path(testset: Path) -> Path:
    return testset.parent / f"judge_calibration_{testset.stem}.csv"


def export_calibration(items, answers, judgments, testset: Path, n: int, seed: int) -> None:
    keys = [k for k in judgments if k in answers]
    rnd = random.Random(seed)
    rnd.shuffle(keys)
    keys = sorted(keys[:n])
    by_id = {it["id"]: it for it in items}
    path = calibration_path(testset)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CALIB_FIELDS)
        w.writeheader()
        for k in keys:
            ans, j = answers[k], judgments[k]
            ref = (answers.get((k[0], "studybot")) or {}).get("ctx_parts") or []
            claims = j.get("claims") or []
            w.writerow({
                "id": k[0], "config": k[1], "question": by_id[k[0]]["question"],
                "context": "\n\n---\n\n".join(ref), "answer": ans["answer"],
                "judge_faithful": int(all(c["supported"] for c in claims)) if claims else "",
                "judge_refused": int(bool(j.get("refused"))),
                "human_faithful": "", "human_refused": "", "note": "",
            })
    print(f"Đã ghi {len(keys)} mẫu vào {path}")
    print("Điền human_faithful (1 = mọi khẳng định đều có căn cứ trong context, 0 = có ý bịa/sai) và")
    print("human_refused (1/0), để trống nếu không chấm được; rồi chạy --calibrate.")


def run_calibration(testset: Path) -> None:
    path = calibration_path(testset)
    if not path.exists():
        sys.exit(f"Chưa có {path}; chạy --export-calibration trước")
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    for field, label in (("faithful", "Faithful"), ("refused", "Refused")):
        pairs = [(r[f"judge_{field}"] == "1", r[f"human_{field}"].strip() == "1") for r in rows
                 if r[f"judge_{field}"].strip() in ("0", "1") and r[f"human_{field}"].strip() in ("0", "1")]
        if not pairs:
            print(f"{label}: chưa có nhãn chấm tay")
            continue
        jv, hv = [p[0] for p in pairs], [p[1] for p in pairs]
        k = cohen_kappa(jv, hv)
        print(f"{label}: n={len(pairs)}  đồng thuận={agreement(jv, hv) * 100:.1f}%  "
              f"kappa={'N/A' if k is None else f'{k:.2f}'}")
        for r, (a, b) in zip([r for r in rows if r[f'judge_{field}'].strip() in ('0', '1')
                              and r[f'human_{field}'].strip() in ('0', '1')], pairs):
            if a != b:
                print(f"   lệch: id={r['id']} {r['config']} judge={int(a)} người={int(b)}  {r['question'][:60]}")


# ─── main ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--testset", type=Path, default=TESTSET)
    ap.add_argument("--n", type=int, default=0, help="chỉ lấy n câu đầu (0 = tất cả)")
    ap.add_argument("--judge-model", default=DEFAULT_JUDGE)
    ap.add_argument("--rpm", type=float, default=12, help="giới hạn số lần gọi Gemini mỗi phút")
    ap.add_argument("--retries", type=int, default=4)
    ap.add_argument("--refresh", action="store_true", help="xóa cache câu trả lời + kết quả chấm của bộ test này")
    ap.add_argument("--skip-generate", action="store_true", help="chỉ chấm/report trên câu trả lời đã có")
    ap.add_argument("--skip-judge", action="store_true")
    ap.add_argument("--export-calibration", action="store_true")
    ap.add_argument("--calib-n", type=int, default=30)
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    testset = args.testset.resolve()
    if args.calibrate:
        run_calibration(testset)
        return

    items = json.loads(testset.read_text(encoding="utf-8"))
    if args.n:
        items = items[:args.n]
    ans_path = CACHE_DIR / f"answers_{testset.stem}.jsonl"
    judge_path = CACHE_DIR / f"judgments_{testset.stem}_{args.judge_model}.jsonl"
    if args.refresh:
        for p in (ans_path, judge_path):
            p.unlink(missing_ok=True)

    limiter = RateLimiter(args.rpm)
    if args.skip_generate:
        answers = load_jsonl(ans_path)
    else:
        answers = asyncio.run(run_generate(items, ans_path, limiter, args.retries))
    if args.skip_judge:
        judgments = load_jsonl(judge_path)
    else:
        judgments = asyncio.run(run_judge(items, answers, judge_path, args.judge_model, limiter, args.retries))

    if args.export_calibration:
        export_calibration(items, answers, judgments, testset, args.calib_n, args.seed)
        return
    write_report(items, answers, judgments, testset, args.judge_model)


if __name__ == "__main__":
    main()
