"""Evaluate an already-running, warm local service. Never loads models or API secrets."""

import argparse
import json
import math
import time
import uuid
from pathlib import Path


def aggregate(rows):
    successful = [r for r in rows if r.get("http_success")]
    steps = [r["steps"] for r in successful if type(r.get("steps")) in (int, float)]
    times = sorted(r["seconds"] for r in successful)
    unknown = [r for r in rows if r.get("kind") == "unanswerable"]
    return {
        "requests": len(rows),
        "http_successes": len(successful),
        "http_failures": len(rows) - len(successful),
        "request_success_rate": len(successful) / len(rows) if rows else None,
        "mean_successful_steps": sum(steps) / len(steps) if steps else None,
        "p95_successful_http_seconds": (
            times[math.ceil(0.95 * len(times)) - 1] if times else None
        ),
        "known_unanswerables": len(unknown),
        "correct_unanswerable_abstentions": sum(
            bool(r.get("http_success") and r.get("refused")) for r in unknown
        ),
        "correct_unanswerable_abstention_rate": (
            sum(bool(r.get("http_success") and r.get("refused")) for r in unknown)
            / len(unknown)
            if unknown
            else None
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8011")
    parser.add_argument("--questions", default="eval/questions.jsonl")
    parser.add_argument("--output", default="reports/live-http.json")
    parser.add_argument("--timeout", type=float, default=360)
    args = parser.parse_args()
    from urllib.parse import urlparse

    if urlparse(args.url).hostname not in ("127.0.0.1", "localhost", "::1"):
        parser.error("Only a local server URL is allowed")
    import httpx

    questions = [
        json.loads(line)
        for line in Path(args.questions).read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    ids = [q["id"] for q in questions]
    if len(set(ids)) != len(ids):
        parser.error("Duplicate question ids")
    run_id = uuid.uuid4().hex
    rows = []
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    def checkpoint():
        report = {
            "config": {
                "url": args.url,
                "timeout": args.timeout,
                "run_id": run_id,
                "planned_questions": len(questions),
            },
            "measurement": "Wall time of POST /chat to already-warmed resident service; no cold-start measurement. No client retry.",
            "warning": "Expected-phrase matching is a substring proxy, not answer accuracy. Human correctness and citation support remain unreviewed. Unanswerable refusal success only measures guard behavior, not all answer quality.",
            "metrics": aggregate(rows),
            "results": rows,
        }
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(output)

    with httpx.Client(timeout=args.timeout, trust_env=False) as client:
        for q in questions:
            row = {
                "id": q["id"],
                "question": q["question"],
                "reference_answer": q.get("reference_answer"),
                "kind": q["kind"],
                "split": q["split"],
                "session_id": "eval-" + run_id + "-" + q["id"],
                "answer": "",
                "sources": [],
                "trace": [],
                "status": None,
                "steps": None,
                "http_success": False,
                "refused": False,
                "manual_correctness": None,
                "manual_citation_support": None,
                "manual_reviewed": False,
                "expected_phrase_proxy": None,
            }
            start = time.perf_counter()
            try:
                response = client.post(
                    args.url.rstrip("/") + "/chat",
                    json={"message": q["question"], "session_id": row["session_id"]},
                )
                row["http_status"] = response.status_code
                if response.is_success:
                    data = response.json()
                    if not isinstance(data, dict) or not isinstance(
                        data.get("answer"), str
                    ):
                        raise ValueError("Invalid chat response")
                    row.update(
                        answer=data["answer"],
                        sources=data.get("sources", []),
                        trace=data.get("trace", []),
                        status=data.get("guard"),
                        steps=data.get("steps"),
                        http_success=True,
                        refused=data.get("guard") == "abstain",
                    )
                    row["expected_phrase_proxy"] = (
                        all(
                            phrase in data["answer"]
                            for phrase in q.get("expected_phrases", [])
                        )
                        if q.get("expected_phrases")
                        else None
                    )
                else:
                    row["status"] = "http-error"
            except (httpx.HTTPError, ValueError, TypeError):
                row["status"] = "transport-or-response-error"
            row["seconds"] = time.perf_counter() - start
            rows.append(row)
            checkpoint()
            print(q["id"], row["status"], "steps=" + str(row["steps"]), flush=True)
    print(json.dumps(aggregate(rows), ensure_ascii=False))


if __name__ == "__main__":
    main()
