"""Merge explicitly supplied human reviews; never infer correctness from generated labels."""

import argparse
import copy
import json
from pathlib import Path


def score_reviews(report, reviews):
    result = copy.deepcopy(report)
    rows = result.get("results", [])
    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate report ids")
    by_id = {r["id"]: r for r in rows}
    seen = set()
    correct = []
    support = []
    for review in reviews:
        key = review.get("id")
        if key not in by_id:
            raise ValueError("Unknown review id")
        if key in seen:
            raise ValueError("Duplicate review id")
        seen.add(key)
        for field in ("correctness", "citation_support"):
            if type(review.get(field)) is not int or review[field] not in (0, 1, 2):
                raise ValueError(field + " must be an integer 0..2")
        notes = review.get("notes", "")
        if not isinstance(notes, str):
            raise ValueError("notes must be text")
        row = by_id[key]
        row.update(
            manual_correctness=review["correctness"],
            manual_citation_support=review["citation_support"],
            manual_reviewed=True,
            manual_notes=notes,
        )
        correct.append(int(review["correctness"] == 2))
        support.append(review["citation_support"] / 2)
    result["human_review"] = {
        "reviewed_count": len(seen),
        "total_count": len(rows),
        "fully_correct_rate": sum(correct) / len(correct) if correct else None,
        "mean_citation_support": sum(support) / len(support) if support else None,
        "scope": "Only explicitly supplied human reviews in this invocation; unreviewed rows excluded.",
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument("reviews")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.resolve() in (Path(args.report).resolve(), Path(args.reviews).resolve()):
        parser.error("output must be a separate path")
    try:
        report = json.loads(Path(args.report).read_text(encoding="utf-8-sig"))
        reviews = [
            json.loads(line)
            for line in Path(args.reviews).read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
        result = score_reviews(report, reviews)
    except (ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result["human_review"], ensure_ascii=False))


if __name__ == "__main__":
    main()
