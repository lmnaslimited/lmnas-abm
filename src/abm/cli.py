from __future__ import annotations

import argparse
import json
from pathlib import Path

from abm.assessment import engine
from abm.workflow import services


def main():
    parser = argparse.ArgumentParser(prog="abm", description="LMNAs unified organization research and assessment workflow")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("discover", help="Run the existing organization discovery pipeline")
    p.add_argument("--regions", nargs="+")
    p.add_argument("--target", type=int)

    p = sub.add_parser("research", help="Prepare the existing organization research package")
    p.add_argument("--org-id", required=True)
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("assess", help="Run a configured assessment workflow")
    assess_sub = p.add_subparsers(dest="assessment_kind", required=True)
    for kind in ("organization", "products"):
        q = assess_sub.add_parser(kind)
        q.add_argument("--org-id", required=True)
        q.add_argument("--all", action="store_true", help="Include all configured product assessments")
        q.add_argument("--dry-run", action="store_true")
        q.add_argument("--package-id")
        q.add_argument("--result-zip", type=Path)
        q.add_argument("--collect", action="store_true")
        q.add_argument("--apply", action="store_true")
        q.add_argument("--confirm", action="store_true")

    p = sub.add_parser("run", help="Execute the organization research and configured assessment workflow")
    p.add_argument("--org-id", required=True)
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("status", help="Show locally recorded workflow artifacts")
    p.add_argument("--org-id", required=True)

    p = sub.add_parser("report", help="Print the consolidated workflow artifact summary")
    p.add_argument("--org-id", required=True)

    p = sub.add_parser("contacts", help="Contact research stages")
    contacts = p.add_subparsers(dest="contacts_command", required=True)
    q = contacts.add_parser("identify", help="Prepare contact identification context (research only)")
    q.add_argument("--org-id", required=True)

    args = parser.parse_args()
    if args.command == "discover":
        return services.discover(args.regions, args.target)
    if args.command == "research":
        return services.research(args.org_id, dry_run=args.dry_run)
    if args.command == "assess":
        if args.collect:
            if not args.package_id or not args.result_zip:
                parser.error("--collect requires --package-id and --result-zip")
            return engine.collect(args.org_id, args.package_id, args.result_zip)
        if args.apply:
            if not args.package_id:
                parser.error("--apply requires --package-id")
            return engine.apply(args.org_id, args.package_id, confirm=args.confirm, dry_run=args.dry_run)
        return engine.run_assessments(args.org_id, args.assessment_kind,
                                      dry_run=args.dry_run or args.assessment_kind == "products")
    if args.command == "run":
        result = services.research(args.org_id, dry_run=args.dry_run)
        if args.dry_run:
            return result
        raise RuntimeError("Full run requires the reviewed research result package between prepare and validated assessment writeback stages")
    if args.command in {"status", "report"}:
        print(json.dumps(services.status(args.org_id), indent=2))
        return 0
    if args.command == "contacts":
        from abm.crm.client import get_doc
        org = get_doc("CRM Organization", args.org_id)
        if org.get("name") != args.org_id:
            raise ValueError(f"CRM Organization not found: {args.org_id}")
        print(json.dumps({"organization_id": args.org_id, "status": "IDENTITY_RESOLVED",
                          "contact_identification": "research-only", "crm_writes": 0}, indent=2))
        return 0


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        import sys
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
