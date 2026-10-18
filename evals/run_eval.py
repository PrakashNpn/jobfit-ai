"""Measure answer and extraction accuracy on the sample data.

Usage (database running, ANTHROPIC_API_KEY set):
    python -m evals.run_eval --ingest   # first run: load data/ into the vector store
    python -m evals.run_eval            # later runs

Each run calls the Claude API (about 13 requests), so it costs a small amount of money.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from app.ingest import split_into_chunks
from app.llm import ClaudeService
from app.store import PgVectorStore

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CASES = json.loads((ROOT / "evals" / "cases.json").read_text())


def ingest_sample_data(store: PgVectorStore) -> None:
    for path in sorted(DATA.glob("*.md")):
        doc_type = "resume" if path.name.startswith("resume") else "job"
        added = store.add(split_into_chunks(path.read_text(), source=path.name, doc_type=doc_type))
        print(f"  ingested {path.name}: {added} chunks")


def grade_answer(answer: str, case: dict) -> bool:
    text = answer.lower()
    if "must_include" in case:
        return all(term.lower() in text for term in case["must_include"])
    return any(term.lower() in text for term in case["must_include_any"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ingest", action="store_true", help="load data/ into the store first")
    args = parser.parse_args()

    store, llm = PgVectorStore(), ClaudeService()
    if args.ingest:
        print("Ingesting sample data...")
        ingest_sample_data(store)

    results = {"ask": [], "extract": []}

    print("\nRAG answers")
    for case in CASES["ask"]:
        chunks = store.search(case["question"], k=5)
        answer = llm.answer(case["question"], chunks)
        passed = grade_answer(answer.answer, case)
        results["ask"].append({**case, "answer": answer.answer, "sources": answer.sources, "passed": passed})
        print(f"  [{'PASS' if passed else 'FAIL'}] {case['question']}")

    print("\nStructured extraction")
    for case in CASES["extract"]:
        job = llm.extract_job((DATA / case["file"]).read_text()).model_dump()
        wrong = {k: {"expected": v, "got": job[k]} for k, v in case["expected"].items() if job[k] != v}
        results["extract"].append({"file": case["file"], "passed": not wrong, "mismatches": wrong})
        print(f"  [{'PASS' if not wrong else 'FAIL'}] {case['file']}" + (f"  {wrong}" if wrong else ""))

    ask_score = sum(r["passed"] for r in results["ask"]) / len(results["ask"])
    extract_score = sum(r["passed"] for r in results["extract"]) / len(results["extract"])
    print(f"\nRAG answer accuracy:   {ask_score:.0%}")
    print(f"Extraction accuracy:   {extract_score:.0%}")

    out_dir = ROOT / "evals" / "results"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"{datetime.now():%Y%m%d-%H%M%S}.json"
    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Saved details to {out_file.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
