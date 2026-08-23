"""Run the boundary corpus and write a report to `evals/results/`.

    python -m evals.run              # run, print summary, write results JSON
    python -m evals.run --no-write   # run and print only
    python -m evals.run --verbose    # also list every case outcome

No API key, no network, no configuration. See evals/README.md.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from evals.harness import Outcome, run_all, summarize

RESULTS_DIR = Path(__file__).parent / "results"

# sqlglot logs a warning when a statement (REPLACE, CREATE TRIGGER, ALTER RENAME)
# falls back to being parsed as a generic Command. That fallback is expected here —
# exp.Command is on the forbidden list precisely to catch it — and the warnings
# bury the report, so quiet them for the run.
logging.getLogger("sqlglot").setLevel(logging.ERROR)


def _print_summary(summary: dict, outcomes: list[Outcome], verbose: bool) -> None:
    print(f"\nboundary corpus — {summary['total_cases']} cases\n")

    header = f"{'class':<24}{'total':>7}{'rejected':>10}{'allowed':>9}{'passed':>8}"
    print(header)
    print("-" * len(header))
    for cls, counts in summary["classes"].items():
        print(
            f"{cls:<24}{counts['total']:>7}{counts['rejected']:>10}"
            f"{counts['allowed']:>9}{counts['passed']:>8}"
        )
    print("-" * len(header))

    adv, adv_ok = summary["adversarial_cases"], summary["adversarial_rejected"]
    leg, leg_ok = summary["legitimate_cases"], summary["legitimate_accepted"]
    print(f"\nadversarial inputs rejected : {adv_ok}/{adv}")
    print(f"legitimate inputs accepted  : {leg_ok}/{leg}")

    if verbose:
        print("\nper-case:")
        for o in outcomes:
            mark = "ok " if o.passed else "FAIL"
            verdict = "rejected" if o.rejected else "allowed"
            print(f"  [{mark}] {o.case.id:<22} {verdict:<9} {o.case.note}")

    if summary["off_contract"]:
        print(
            "\nnote — rejected, but not via the validator's documented exception type:\n  "
            + ", ".join(summary["off_contract"])
        )

    if summary["failures"]:
        print("\nFAILURES:")
        for o in outcomes:
            if not o.passed:
                want = "reject" if o.case.should_reject else "allow"
                got = "rejected" if o.rejected else "allowed"
                print(f"  {o.case.id}: expected {want}, got {got} — {o.case.note}")
                print(f"    input: {o.case.input!r}")
    else:
        print("\nall cases behaved as expected.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-write", action="store_true", help="don't write a results file")
    parser.add_argument("--verbose", action="store_true", help="list every case outcome")
    args = parser.parse_args(argv)

    outcomes = run_all()
    summary = summarize(outcomes)
    _print_summary(summary, outcomes, args.verbose)

    if not args.no_write:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        out = RESULTS_DIR / f"{stamp}.json"
        out.write_text(
            json.dumps(
                {
                    "generated_at": stamp,
                    "summary": summary,
                    "cases": [o.to_dict() for o in outcomes],
                },
                indent=2,
            )
            + "\n"
        )
        print(f"\nwrote {out.relative_to(Path.cwd()) if out.is_relative_to(Path.cwd()) else out}")

    return 1 if summary["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
