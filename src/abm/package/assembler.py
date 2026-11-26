"""Deterministic, content-addressed research package assembly."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


class PackageAssembler:
    """Assemble a package from already retrieved CRM read context.

    `creation_metadata` is intentionally excluded from deterministic content
    checksums and may carry a timestamp supplied by the caller.
    """

    VERSION = "1.0"

    def assemble(self, configuration: dict, run_context: dict, *, output_dir: str | Path | None = None) -> dict:
        template = configuration.get("assessment_template") or configuration.get("template") or {}
        prompt = template.get("master_prompt")
        contract = template.get("result_contract")
        if not isinstance(prompt, str) or not isinstance(contract, str):
            raise ValueError("CRM template must contain string master_prompt and result_contract fields")
        questions = configuration.get("assessment_questions", template.get("assessment_questions", []))
        content: dict[str, bytes] = {
            "run_context.json": _canonical(run_context),
            "master_prompt.md": prompt.encode("utf-8"),
            "result_contract.json": contract.encode("utf-8"),
            "template_snapshot.json": _canonical(template),
            "questions.json": _canonical(questions),
            "organization_context.json": _canonical(configuration.get("organization")),
            "source_catalogue.json": _canonical(configuration.get("source_catalogue", {})),
            "research_plan.json": _canonical(configuration.get("research_plan", {})),
        }
        if configuration.get("organization") is None:
            del content["organization_context.json"]
        hashes = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(content.items())}
        manifest = {"package_schema_version": self.VERSION,
                    "template_name": template.get("name"),
                    "template_modified": template.get("modified"),
                    "source_identities": sorted(configuration.get("source_catalogue", {})),
                    "files": sorted(content),
                    "creation_metadata": configuration.get("creation_metadata", {})}
        content["checksums.json"] = _canonical(hashes)
        content["manifest.json"] = _canonical(manifest)
        if output_dir is not None:
            target = Path(output_dir)
            target.mkdir(parents=True, exist_ok=False)
            for name, data in content.items():
                (target / name).write_bytes(data)
        return {"manifest": manifest, "checksums": hashes,
                "files": {name: data for name, data in content.items()}}
