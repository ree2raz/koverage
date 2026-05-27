"""Underwriter CLI.

  python -m underwriter.cli run               # full live eval (needs OPENROUTER_API_KEY)
  python -m underwriter.cli run --smoke       # 2 prompts/suite, guard off — cheap sanity check
  python -m underwriter.cli demo              # synthetic scorecard → PDF + web (no API calls)
  python -m underwriter.cli report <path>     # regenerate PDF + publish from a scorecard.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .report import generate_pdf, publish_scorecard, synthetic_scorecard
from .results import Scorecard
from .runner import run

_RUNS = Path(__file__).resolve().parents[1] / "runs"


def cmd_run(args: argparse.Namespace) -> None:
    guard_options = (False,) if args.no_guard else (False, True)
    suites = args.suites.split(",") if args.suites else None
    n = 2 if args.smoke else args.n
    if args.smoke:
        guard_options = (False,)
    scorecard, run_dir = run(suites=suites, n_per_suite=n, guard_options=guard_options)
    pdf = generate_pdf(scorecard, run_dir / "scorecard.pdf")
    web = publish_scorecard(scorecard)
    print(f"PDF  → {pdf}\nweb  → {web}")


def cmd_demo(_: argparse.Namespace) -> None:
    sc = synthetic_scorecard()
    out = _RUNS / "demo"
    out.mkdir(parents=True, exist_ok=True)
    (out / "scorecard.json").write_text(sc.model_dump_json(indent=2))
    pdf = generate_pdf(sc, out / "scorecard.pdf")
    web = publish_scorecard(sc)
    print(f"synthetic scorecard → {out/'scorecard.json'}\nPDF → {pdf}\nweb → {web}")


def cmd_report(args: argparse.Namespace) -> None:
    sc = Scorecard.model_validate_json(Path(args.path).read_text())
    pdf = generate_pdf(sc, Path(args.path).with_suffix(".pdf"))
    web = publish_scorecard(sc)
    print(f"PDF → {pdf}\nweb → {web}")


def main() -> None:
    p = argparse.ArgumentParser(prog="underwriter")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the live evaluation")
    r.add_argument("--suites", help="comma-separated subset (factual,jailbreak,bias,sensitive)")
    r.add_argument("--n", type=int, default=None, help="cap prompts per suite")
    r.add_argument("--no-guard", action="store_true", help="skip the guardrail-on pass")
    r.add_argument("--smoke", action="store_true", help="2 prompts/suite, guard off (cheap)")
    r.set_defaults(func=cmd_run)

    d = sub.add_parser("demo", help="synthetic scorecard → PDF + web (no API calls)")
    d.set_defaults(func=cmd_demo)

    rep = sub.add_parser("report", help="regenerate PDF + publish from a scorecard.json")
    rep.add_argument("path")
    rep.set_defaults(func=cmd_report)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
