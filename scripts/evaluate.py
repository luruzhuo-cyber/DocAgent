import argparse, json, time, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from docagent.config import load_settings
from docagent.retrieval import Retriever

p = argparse.ArgumentParser()
p.add_argument("--strategy", choices=["fixed", "structural"], default="structural")
p.add_argument("--mode", choices=["bm25", "dense", "hybrid"], default="bm25")
p.add_argument("--rerank", action="store_true")
p.add_argument("--live", action="store_true")
p.add_argument("--split", choices=["dev", "test", "all"], default="all")
p.add_argument("--output", default="reports/evaluation.json")
args = p.parse_args()
s = load_settings()
if args.live and not s.llm_api_key:
    p.error("--live requires a configured LLM_API_KEY; no answer evaluation was run")
r = Retriever(s, mode=args.mode, strategy=args.strategy)
questions = [
    json.loads(line)
    for line in Path("eval/questions.jsonl").read_text(encoding="utf-8").splitlines()
]
results = []
engine = None
if args.live:
    from docagent.engine import Engine

    s.use_rerank = args.rerank
    engine = Engine(s, r)
for q in questions:
    if args.split != "all" and q["split"] != args.split:
        continue
    start = time.perf_counter()
    found = r.search(q["question"], mode=args.mode, top_k=5, rerank=args.rerank)
    hits = found["hits"]
    expected = q["expected_evidence"]

    def matches(h, e):
        return h["document"] == e["document"] and (
            e["section"] is None or e["section"] in h.get("sections", [h["section"]])
        )

    covered = sum(any(matches(h, e) for h in hits) for e in expected)
    rank = next(
        (i + 1 for i, h in enumerate(hits) if any(matches(h, e) for e in expected)),
        None,
    )
    row = dict(
        id=q["id"],
        question=q["question"],
        reference_answer=q.get("reference_answer"),
        split=q["split"],
        kind=q["kind"],
        ranked_ids=[h["id"] for h in hits],
        retrieval_seconds=time.perf_counter() - start,
        hit_at_5=int(covered > 0) if expected else None,
        recall_at_5=covered / len(expected) if expected else None,
        mrr=1 / rank if rank else (0 if expected else None),
        manual_correctness=None,
        manual_citation_support=None,
        manual_reviewed=False,
    )
    if args.live:
        from docagent.engine import Engine

        live_start = time.perf_counter()
        events = list(
            engine.events(q["question"], "eval-" + q["id"] + "-" + str(time.time_ns()))
        )
        row["events"] = events
        row["total_seconds"] = time.perf_counter() - live_start
        answer = next(
            (
                e["data"].get("answer", "")
                for e in reversed(events)
                if e["event"] == "done"
            ),
            "",
        )
        done = next((e["data"] for e in reversed(events) if e["event"] == "done"), {})
        row["steps"] = done.get("steps")
        row["refused"] = done.get("guard") == "abstain"
        row["successful"] = bool(done) and not any(
            e["event"] == "error" for e in events
        )
        row["expected_phrase_proxy"] = (
            all(t in answer for t in q["expected_phrases"])
            if q["expected_phrases"]
            else None
        )
        row["proxy_warning"] = (
            "Substring proxy is not factual accuracy; human review required."
        )
    results.append(row)


def avg(key):
    values = [r[key] for r in results if r[key] is not None]
    return sum(values) / len(values) if values else None


report = {
    "config": vars(args),
    "label_warning": "Agent-authored fact-specific labels were checked against pinned source prose, not human reviewed. Test is provisional, not a production benchmark.",
    "rubric": {
        "manual_correctness": "Human: 0 incorrect, 1 partly correct, 2 fully correct. Calculation must match exact result. Unanswerable must abstain.",
        "manual_citation_support": "Human: 0 unsupported, 1 partial, 2 every material claim supported by returned current-turn evidence.",
        "multi": "Recall denominator counts expected document/section pairs, not all possible equivalent chunks.",
    },
    "metrics": {
        k: avg(k) for k in ("hit_at_5", "recall_at_5", "mrr", "retrieval_seconds")
    },
    "retrieval_evaluable": sum(
        bool(q["expected_evidence"])
        for q in questions
        if args.split == "all" or q["split"] == args.split
    ),
    "results": results,
}
if args.live:
    totals = sorted(row["total_seconds"] for row in results)
    steps = [
        row["steps"]
        for row in results
        if row.get("successful") and isinstance(row.get("steps"), (int, float))
    ]
    report["live"] = {
        "timing_scope": "warm retrieval; excludes preflight search; includes model requests and tool execution",
        "model": s.llm_model,
        "base_url": s.llm_base_url,
        "p95_total_seconds": (
            totals[max(0, __import__("math").ceil(0.95 * len(totals)) - 1)]
            if totals
            else None
        ),
        "average_successful_steps": sum(steps) / len(steps) if steps else None,
    }
import hashlib, platform

manifest = Path(s.corpus_dir) / "provenance.json"
report["provenance"] = {
    "corpus_commit": (
        json.loads(manifest.read_text(encoding="utf-8-sig"))["commit"]
        if manifest.exists()
        else None
    ),
    "questions_sha256": hashlib.sha256(
        Path("eval/questions.jsonl").read_bytes()
    ).hexdigest(),
    "embedding_model": s.embedding_model,
    "reranker_model": s.reranker_model,
    "python": platform.python_version(),
}
latencies = sorted(row["retrieval_seconds"] for row in results)
report["metrics"]["p95_retrieval_seconds"] = (
    latencies[max(0, __import__("math").ceil(0.95 * len(latencies)) - 1)]
    if latencies
    else None
)
report["first_query_seconds"] = results[0]["retrieval_seconds"] if results else None
Path(args.output).parent.mkdir(parents=True, exist_ok=True)
Path(args.output).write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(report["metrics"], ensure_ascii=False))
