from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = APP_ROOT.parent
DISCOVERY = WORKSPACE_ROOT / "lmnas_discovery_pipeline" / "src" / "pipeline.py"
ORCHESTRATOR = WORKSPACE_ROOT / "lmnas-crm-research-orchestrator" / "src" / "orchestrator.py"


def _run(script: Path, args: list[str]):
    if not script.exists():
        raise RuntimeError(f"Existing component entry point not found: {script}")
    return subprocess.run([sys.executable, str(script), *args], cwd=script.parent.parent,
                          check=True).returncode


def discover(regions: list[str] | None = None, target: int | None = None):
    args = ["prepare"]
    if regions:
        args += ["--regions", *regions]
    if target is not None:
        args += ["--target", str(target)]
    return _run(DISCOVERY, args)


def research(org_id: str, *, dry_run: bool = False):
    from abm.assessment.engine import prepare
    return prepare(org_id, dry_run=dry_run)


def status(org_id: str):
    base = WORKSPACE_ROOT / "lmnas_discovery_pipeline" / "workspace"
    summary = {"organization_id": org_id, "discovery_runs": [], "assessment_packages": []}
    runs = base / "runs"
    if runs.exists():
        for manifest_path in runs.glob("*/manifest.json"):
            try:
                manifest = json.loads(manifest_path.read_text())
                if org_id.casefold() in json.dumps(manifest).casefold():
                    summary["discovery_runs"].append(str(manifest_path.parent))
            except (OSError, json.JSONDecodeError):
                continue
    outgoing = WORKSPACE_ROOT / "lmnas-crm-research-orchestrator" / "workspace" / "outgoing"
    org_slug = "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in org_id).split())
    path = outgoing / org_slug
    if path.exists():
        summary["assessment_packages"] = sorted(str(p) for p in path.iterdir() if p.is_dir())
    return summary

