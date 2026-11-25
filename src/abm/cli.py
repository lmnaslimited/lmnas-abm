"""Command line foundation; execution workflows are intentionally not implemented."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Sequence


ASSESSMENT_OPERATIONS = ("CREATE", "UPDATE")
RESEARCH_STAGES = ("DISCOVERY", "FULL_ASSESSMENT")


@dataclass(frozen=True)
class RunCommand:
    assessment_operation: str
    research_stage: str | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="abm",
        description="LMNAs ABM workflow foundation (CRM and research execution are not configured)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Validate an ABM run request")
    run.add_argument(
        "--assessment-operation",
        required=True,
        type=str.upper,
        choices=ASSESSMENT_OPERATIONS,
        help="Required assessment operation: CREATE or UPDATE",
    )
    run.add_argument(
        "--research-stage",
        type=str.upper,
        choices=RESEARCH_STAGES,
        help="Optional research stage, independent of assessment operation",
    )
    return parser


def parse_command(argv: Sequence[str] | None = None) -> RunCommand:
    args = build_parser().parse_args(argv)
    if args.command != "run":
        raise AssertionError("argparse accepted an unsupported command")
    return RunCommand(
        assessment_operation=args.assessment_operation,
        research_stage=args.research_stage,
    )


def main(argv: Sequence[str] | None = None) -> int:
    command = parse_command(argv)
    print(
        "Command validated. No CRM or research operation was performed. "
        f"assessment_operation={command.assessment_operation} "
        f"research_stage={command.research_stage or 'UNSPECIFIED'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
