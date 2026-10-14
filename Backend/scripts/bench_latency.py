"""
bench_latency.py — Đo độ trễ end-to-end của /api/chat/stream.

Mỗi câu hỏi chạy trong một session mới (lượt đầu → giống người dùng mở chat mới).
Đo: TTFT (chunk nội dung đầu tiên), tổng thời gian tới [DONE].
Sau khi chạy, in thêm p50/p95 từng bước từ /api/chat/perf/stats.

Cách dùng (server đang chạy ở localhost:8000):
    python scripts/bench_latency.py
    python scripts/bench_latency.py --repeat 2 --clear-cache --out bench_before.json
"""
import argparse
import json
import statistics
import time
import uuid

import httpx

DEFAULT_QUESTIONS = [
    "Điều kiện để được xét tốt nghiệp là gì?",
    "Cách tính điểm trung bình tích lũy CPA?",
    "Sinh viên bị cảnh báo học tập khi nào?",
    "Học phí một tín chỉ là bao nhiêu?",
    "Thủ tục xin bảo lưu kết quả học tập như thế nào?",
    "đrl bao nhiêu thì được xét học bổng?",
    "Điều kiện đăng ký học vượt?",
    "Quy định về thi lại và học lại học phần?",
]


def run_one(client: httpx.Client, base: str, question: str) -> dict:
    session_id = str(uuid.uuid4())
    t0 = time.perf_counter()
    ttft = None
    chars = 0
    with client.stream(
        "POST", f"{base}/api/chat/stream",
        json={"session_id": session_id, "question": question},
        timeout=120,
    ) as r:
        r.raise_for_status()
        buf = ""
        for text in r.iter_text():
            buf += text
            *events, buf = buf.split("\n\n")
            for ev in events:
                ev = ev.strip()
                if not ev.startswith("data: "):
                    continue
                data = ev[6:]
                if data == "[DONE]":
                    total = (time.perf_counter() - t0) * 1000
                    return {"question": question, "ttft_ms": round(ttft or total, 1),
                            "total_ms": round(total, 1), "chars": chars}
                if data.startswith("["):
                    continue
                if ttft is None:
                    ttft = (time.perf_counter() - t0) * 1000
                chars += len(data)
    total = (time.perf_counter() - t0) * 1000
    return {"question": question, "ttft_ms": round(ttft or total, 1), "total_ms": round(total, 1),
            "chars": chars, "incomplete": True}


def pct(values: list[float], p: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, round(p / 100 * (len(s) - 1)))]


def main():
    ap = argparse.ArgumentParser()
    # Dùng 127.0.0.1: trên Windows "localhost" thử IPv6 trước → mỗi kết nối chậm thêm ~2s
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--clear-cache", action="store_true", help="Xóa semantic cache + perf stats trước khi chạy")
    ap.add_argument("--out", help="Ghi kết quả ra file JSON")
    args = ap.parse_args()

    with httpx.Client() as client:
        if args.clear_cache:
            client.delete(f"{args.base}/api/chat/cache/clear")
            client.delete(f"{args.base}/api/chat/perf/clear")

        results = []
        for rnd in range(args.repeat):
            for q in DEFAULT_QUESTIONS:
                res = run_one(client, args.base, q)
                res["round"] = rnd + 1
                results.append(res)
                print(f"[r{rnd + 1}] ttft={res['ttft_ms']:>8.0f}ms  total={res['total_ms']:>8.0f}ms  {q}")

        ttfts = [r["ttft_ms"] for r in results]
        totals = [r["total_ms"] for r in results]
        summary = {
            "n": len(results),
            "ttft_p50": round(statistics.median(ttfts), 1),
            "ttft_p95": round(pct(ttfts, 95), 1),
            "total_p50": round(statistics.median(totals), 1),
            "total_p95": round(pct(totals, 95), 1),
        }
        print("\nSUMMARY:", json.dumps(summary, ensure_ascii=False))

        stages = client.get(f"{args.base}/api/chat/perf/stats").json().get("stats", {})
        print("\nSERVER STAGES (ms):")
        for name, st in (stages.get("stages_ms") or {}).items():
            print(f"  {name:<12} p50={st['p50']:>8}  p95={st['p95']:>8}  n={st['count']}")

        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump({"summary": summary, "results": results, "server_stages": stages},
                          f, ensure_ascii=False, indent=2)
            print(f"\nĐã lưu {args.out}")


if __name__ == "__main__":
    main()
