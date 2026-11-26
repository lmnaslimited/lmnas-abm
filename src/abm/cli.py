"""Command-line validation and regional research-package preparation."""

from __future__ import annotations

import argparse
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from abm.config import DEFAULT_CONFIG_PATH, ConfigurationError, load_config
from abm.package.preparation import ResearchPackagePreparer


ASSESSMENT_OPERATIONS = ("CREATE", "UPDATE")
RESEARCH_STAGES = ("DISCOVERY", "FULL_ASSESSMENT")


@dataclass(frozen=True)
class RunCommand:
    assessment_operation: str
    research_stage: str | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="abm",
        description="Prepare CRM-backed regional research packages; research execution is not implemented",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Validate a run request; does not execute research")
    run.add_argument(
        "--assessment-operation", required=True, type=str.upper,
        choices=ASSESSMENT_OPERATIONS, help="Assessment operation: CREATE or UPDATE",
    )
    run.add_argument(
        "--research-stage", type=str.upper, choices=RESEARCH_STAGES,
        help="Research stage, independent of assessment operation",
    )

    prepare = subparsers.add_parser(
        "prepare", help="Prepare an immutable regional CREATE research package"
    )
    prepare.add_argument(
        "--assessment-operation", required=True, type=str.upper,
        choices=ASSESSMENT_OPERATIONS, help="Only CREATE preparation is currently supported",
    )
    prepare.add_argument(
        "--research-stage", required=True, type=str.upper,
        choices=RESEARCH_STAGES, help="Research stage to record in the package run context",
    )
    prepare.add_argument("--template", help="CRM Assessment Template name; overrides configuration")
    prepare.add_argument("--region", help="Regional CRM Territory name; overrides configuration")
    prepare.add_argument("--output-dir", type=Path, help="Package output root; overrides configuration")
    prepare.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG_PATH,
        help=f"Non-secret TOML configuration file (default: {DEFAULT_CONFIG_PATH})",
    )
    return parser


def parse_command(argv: Sequence[str] | None = None) -> RunCommand:
    args = build_parser().parse_args(argv)
    if args.command != "run":
        raise AssertionError("parse_command only accepts the run command")
    return RunCommand(
        assessment_operation=args.assessment_operation,
        research_stage=args.research_stage,
    )


def main(
    argv: Sequence[str] | None = None, *,
    preparer_factory: Callable[[], ResearchPackagePreparer] | None = None,
    output: Callable[[str], None] = print,
    error_output: Callable[[str], None] | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    emit_error = error_output or (lambda message: print(message, file=sys.stderr))
    if args.command == "run":
        output(
            "Command validated. No CRM or research operation was performed. "
            f"assessment_operation={args.assessment_operation} "
            f"research_stage={args.research_stage or 'UNSPECIFIED'}"
        )
        return 0

    if args.assessment_operation != "CREATE":
        emit_error("UPDATE package preparation is unsupported; no CRM or research operation was performed.")
        return 2
    try:
        config = load_config(args.config)
        template = args.template or config.organization_assessment_template
        region = args.region or config.regional_territory
        output_root = args.output_dir or config.package_output_dir
        missing = [label for label, value in (
            ("template", template), ("region", region), ("package output directory", output_root)
        ) if not value]
        if missing:
            raise ConfigurationError(
                f"Missing required {', '.join(missing)}; set [defaults] in {args.config} "
                "or pass the corresponding CLI option."
            )

        now = datetime.now(timezone.utc)
        run_id = f"{now:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
        package_dir = Path(output_root) / run_id
        run_context = {
            "run_id": run_id,
            "assessment_operation": "CREATE",
            "research_stage": args.research_stage,
            "run_territory": region,
            "scope_type": "region",
            "creation_metadata": {"created_at": now.isoformat()},
        }
        preparer = (preparer_factory or ResearchPackagePreparer)()
        package = preparer.prepare_create(
            template, run_context, run_territory=region,
            scope_type="region", output_dir=package_dir,
        )
    except (ConfigurationError, OSError, RuntimeError, ValueError) as exc:
        emit_error(f"Package preparation failed: {exc}")
        return 2

    summary = package["preparation_summary"]
    output(f"Package: {package_dir}")
    output("Assessment operation: CREATE")
    output(f"Research stage: {args.research_stage}")
    output(f"Template: {template}")
    output(f"Region: {region}")
    output(
        "Sources: "
        f"retrieved={summary['catalogue_retrieved']} "
        f"selected={summary['applicable_selected']} "
        f"excluded={summary['excluded']}"
    )
    output("Phases:")
    for phase in summary["phase_counts"]:
        territory = phase["territory"] or "global"
        noun = "source" if phase["source_count"] == 1 else "sources"
        output(f"  {phase['phase']} ({territory}): {phase['source_count']} {noun}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
