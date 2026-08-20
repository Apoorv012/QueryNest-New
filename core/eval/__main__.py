from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from core.eval.report import generate_report, print_report
from core.eval.runner import run_eval


def main() -> None:
    golden_path = Path("data/eval/golden.json")
    if not golden_path.exists():
        print(f"Golden dataset not found: {golden_path}")
        sys.exit(1)

    print("Running evaluation...")
    results = run_eval(golden_path)

    print_report(results)

    reports_dir = Path("reports")
    report_path = generate_report(results, reports_dir)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
