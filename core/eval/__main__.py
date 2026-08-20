from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

# BM25 (core.eval.baselines) connects to Postgres directly rather than
# through the API, so it needs QUERYNEST_STORAGE_MODE and the relevant
# connection-string var loaded the same way core.api.main loads them.
load_dotenv()

from core.eval.baselines import run_eval_bm25
from core.eval.report import generate_report, print_comparison, print_report
from core.eval.runner import run_eval


def main() -> None:
    # Optional path argument so alternate query sets can be evaluated, e.g.
    #   python -m core.eval data/eval/golden_paraphrased.json
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    golden_path = Path(args[0]) if args else Path("data/eval/golden.json")
    if not golden_path.exists():
        print(f"Golden dataset not found: {golden_path}")
        sys.exit(1)
    print(f"Golden set: {golden_path}")

    print("Running evaluation (semantic)...")
    results = run_eval(golden_path)

    print_report(results)

    print("\nRunning evaluation (BM25 baseline)...")
    bm25_results = run_eval_bm25(golden_path)

    print_comparison(results, bm25_results)

    reports_dir = Path("reports")
    report_path = generate_report(results, reports_dir, bm25_results=bm25_results)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
