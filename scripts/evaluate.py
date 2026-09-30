"""Evaluate through the API. Optional baseline and W&B are never used in chat."""

import argparse
import json
import os
import statistics
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


def looks_like_abstention(text):
    text = text.lower()
    return any(
        phrase in text
        for phrase in (
            "tidak menemukan",
            "tidak ditemukan",
            "tidak tersedia",
            "tidak disebutkan",
            "tidak tercantum",
            "tidak ada informasi",
            "tidak tahu",
            "informasi yang cukup",
        )
    )


def score_case(case, response):
    answer = response["jawaban"].lower()
    expected = {(item["source"], item["page"]) for item in case["expected_sources"]}
    retrieved = {(item["source"], item["page"]) for item in response["referensi"]}
    cited = {(item["source"], item["page"]) for item in response["referensi"] if item.get("cited")}
    keywords = case["expected_keywords"]
    return {
        "keyword_coverage": sum(keyword.lower() in answer for keyword in keywords) / len(keywords)
        if keywords
        else None,
        "source_recall": len(expected & retrieved) / len(expected) if expected else None,
        "citation_precision": len(cited & expected) / len(cited)
        if cited
        else (0.0 if expected else None),
        "abstention_correct": looks_like_abstention(answer) == case["expected_abstain"],
    }


def main():
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument(
        "--api-url", default=os.getenv("RAG_API_URL", "http://127.0.0.1:8000/api/v1")
    )
    parser.add_argument("--output", type=Path, default=Path("evaluations/results.json"))
    parser.add_argument(
        "--compare-baseline",
        action="store_true",
        help="Satu panggilan Gemini tambahan per kasus (berbiaya).",
    )
    parser.add_argument(
        "--wandb",
        action="store_true",
        help="Kirim metrik agregat ke W&B; membutuhkan requirements-eval.txt.",
    )
    parser.add_argument(
        "--log-content",
        action="store_true",
        help="Juga kirim pertanyaan/jawaban ke W&B jika --wandb dipilih.",
    )
    args = parser.parse_args()
    if args.log_content and not args.wandb:
        parser.error("--log-content membutuhkan --wandb")
    cases = [
        json.loads(line)
        for line in args.dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not cases:
        parser.error("Dataset kosong")
    session = requests.Session()
    if key := os.getenv("RAG_CLIENT_API_KEY"):
        session.headers["X-API-Key"] = key
    timeout = (5, 300)

    def request(method, path, **kwargs):
        # Respect the backend limiter; never automatically retry an upload/provider error.
        for _ in range(3):
            response = session.request(
                method, args.api_url.rstrip("/") + path, timeout=timeout, **kwargs
            )
            if response.status_code != 429 or method != "POST" or path != "/chat":
                response.raise_for_status()
                return response.json()
            time.sleep(min(60, max(1, int(response.headers.get("Retry-After", "60")))))
        response.raise_for_status()

    documents = {}
    for name in sorted({name for case in cases for name in case["documents"]}):
        path = (args.dataset.parent / name).resolve()
        if not path.is_relative_to(args.dataset.parent.resolve()):
            parser.error("Dokumen dataset harus berada di dalam folder dataset")
        with path.open("rb") as file:
            result = request(
                "POST", "/upload", files={"file": (path.name, file, "application/pdf")}
            )
        documents[name] = result["document"]["id"]
    baseline = None
    if args.compare_baseline:
        from langchain_google_genai import ChatGoogleGenerativeAI

        baseline = ChatGoogleGenerativeAI(
            model=os.getenv("RAG_MODEL", "gemini-2.5-flash"),
            temperature=0,
            timeout=60,
            max_retries=2,
            max_output_tokens=2048,
        )
    results = []
    for case in cases:
        response = request(
            "POST",
            "/chat",
            json={
                "pertanyaan": case["question"],
                "document_ids": [documents[name] for name in case["documents"]],
            },
        )
        row = {
            "id": case["id"],
            "question": case["question"],
            "response": response,
            "scores": score_case(case, response),
        }
        if baseline:
            start = time.perf_counter()
            pure = baseline.invoke(case["question"])
            # AIMessage.text normalizes both plain and structured content.
            baseline_scores = score_case(case, {"jawaban": pure.text, "referensi": []})
            row["baseline"] = {
                "answer": pure.text,
                "latency_ms": round((time.perf_counter() - start) * 1000),
                "usage": pure.usage_metadata,
                "scores": {
                    key: baseline_scores[key] for key in ("keyword_coverage", "abstention_correct")
                },
            }
        results.append(row)
        print(f"Selesai {case['id']}", flush=True)
    summary = {
        "cases": len(results),
        "mean_latency_ms": statistics.mean(
            row["response"]["metrics"]["latency_ms"] for row in results
        ),
    }
    for metric in ("keyword_coverage", "source_recall", "citation_precision", "abstention_correct"):
        values = [row["scores"][metric] for row in results if row["scores"][metric] is not None]
        summary[metric] = statistics.mean(values) if values else None
    if baseline:
        summary["baseline_mean_latency_ms"] = statistics.mean(
            row["baseline"]["latency_ms"] for row in results
        )
        for metric in ("keyword_coverage", "abstention_correct"):
            values = [
                row["baseline"]["scores"][metric]
                for row in results
                if row["baseline"]["scores"][metric] is not None
            ]
            summary["baseline_" + metric] = statistics.mean(values) if values else None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if args.wandb:
        import wandb

        with wandb.init(project="rag-gemini-evaluation") as run:
            run.log(summary)
            if args.log_content:
                table = wandb.Table(columns=["id", "question", "rag_answer", "baseline_answer"])
                for row in results:
                    table.add_data(
                        row["id"],
                        row["question"],
                        row["response"]["jawaban"],
                        row.get("baseline", {}).get("answer", ""),
                    )
                run.log({"answers": table})
    print(json.dumps(summary, indent=2))
    print(
        f"Hasil lokal: {args.output}. Skor otomatis adalah proxy, bukan penilaian factuality final."
    )


if __name__ == "__main__":
    main()
