from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from abm.crm import client

AI_FIELDS = ("ai_rating", "ai_evidence_status", "ai_confidence", "ai_supporting_evidence")
APP_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = APP_ROOT.parent
ORCHESTRATOR = WORKSPACE_ROOT / "lmnas-crm-research-orchestrator" / "src" / "orchestrator.py"


@dataclass(frozen=True)
class AssessmentConfig:
    key: str
    label: str
    template: str
    reference_doctype: str
    folder: str
    product_context: str | None = None


def _load_orchestrator():
    if not ORCHESTRATOR.exists():
        raise RuntimeError(f"Existing research orchestrator was not found: {ORCHESTRATOR}")
    sys.path.insert(0, str(ORCHESTRATOR.parent))
    spec = importlib.util.spec_from_file_location("abm_existing_orchestrator", ORCHESTRATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configurations() -> dict[str, AssessmentConfig]:
    # Template names and folders remain owned by the orchestrator configuration.
    source_cfg = _load_orchestrator().assessment_config()
    product_templates = {
        "02-lens-cpq": "CRM Product",
        "03-tender-intelligence": "CRM Product",
        "04-lensips": "CRM Product",
    }
    configs = {}
    for template, meta in source_cfg.items():
        key = meta["folder"]
        reference_doctype = "CRM Organization" if key == "01-organisation" else product_templates.get(key)
        if reference_doctype is None:
            raise ValueError(f"No verified reference DocType mapping for configured assessment {key!r}")
        configs[key] = AssessmentConfig(key, meta["label"], template, reference_doctype, meta["folder"])
    return configs


def load_template(config: AssessmentConfig, org_id: str) -> dict[str, Any]:
    """Resolve existing assessment records using the established orchestrator rules."""
    module = _load_orchestrator()
    org = client.get_doc("CRM Organization", org_id)
    if not isinstance(org, dict) or org.get("name") != org_id:
        raise ValueError(f"CRM Organization not found: {org_id}")
    if config.reference_doctype == "CRM Organization":
        assessments = module.get_assessments(org_id, org)
        matches = [doc for _, doc, _ in assessments if doc.get("assessment_template") == config.template]
    else:
        # Product assessments belong to product documents, not the CRM Organization.
        # The orchestrator resolver intentionally covers its known four records only.
        # Do not synthesize product identity filters or record-creation rules without metadata.
        raise RuntimeError("Product assessment reference identity is not represented in the existing organization resolver; live metadata and documented lookup rules are required")
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one existing assessment for {config.template}; found {len(matches)}")
    return matches[0]


def validate_result(org_id: str, assessment_id: str, config: AssessmentConfig, result: dict):
    meta = {"assessment_template": config.template,
            "question_row_ids": [q["name"] for q in result.get("_live_questions", [])]}
    if not meta["question_row_ids"]:
        doc = client.get_doc("CRM Assessment", assessment_id)
        meta["question_row_ids"] = [q.get("name") for q in doc.get("assessment_questions", [])]
    return _load_orchestrator().validate_result(org_id, assessment_id, meta, result)


def prepare(org_id: str, *, dry_run: bool = False):
    return _load_orchestrator().prepare(org_id, dry_run=dry_run)


def collect(org_id: str, package_id: str, result_zip: Path):
    return _load_orchestrator().collect(org_id, package_id, result_zip)


def apply(org_id: str, package_id: str, *, confirm: bool = False, dry_run: bool = False):
    """Delegate validation, full preflight, AI-only writes and receipt to source implementation."""
    return _load_orchestrator().apply(org_id, package_id, confirm=confirm, dry_run=dry_run)


def run_assessments(org_id: str, kind: str, *, dry_run: bool = True):
    """Prepare the established four-assessment package, filtered by configuration."""
    configs = configurations()
    if kind == "organization":
        selected = [cfg for cfg in configs.values() if "organisation" in cfg.key or "organization" in cfg.key]
    elif kind == "products":
        selected = [cfg for cfg in configs.values() if cfg.reference_doctype == "CRM Product"]
    else:
        raise ValueError(f"Unsupported assessment group: {kind}")
    if not selected:
        raise RuntimeError(f"No assessment configuration found for {kind}; inspect source config")
    if kind == "organization":
        # Existing orchestrator prepares all four as one indivisible research package.
        # Keep that validated methodology intact rather than synthesizing an alternate package.
        return prepare(org_id, dry_run=dry_run)
    # Product-only package partitioning is not supported by the source manifest contract.
    # Verify all configured records, then report product records in dry-run mode.
    raise RuntimeError("Product assessment dry-run is blocked until live CRM metadata and existing product assessment lookup rules are verified; no CRM changes made")

