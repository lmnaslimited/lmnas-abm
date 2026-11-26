"""Deterministic, content-addressed research package assembly."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


class PackageAssembler:
    """Assemble a package from already retrieved CRM read context.

    `creation_metadata` is intentionally excluded from deterministic content
    checksums and may carry a timestamp supplied by the caller. Its ZIP is
    written inside the package directory and excludes itself.
    """

    VERSION = "2.0"

    def assemble(self, configuration: dict, run_context: dict, *, output_dir: str | Path | None = None) -> dict:
        template = configuration.get("assessment_template") or configuration.get("template") or {}
        prompt = template.get("master_prompt")
        contract = template.get("result_contract")
        if not isinstance(prompt, str) or not isinstance(contract, str):
            raise ValueError("CRM template must contain string master_prompt and result_contract fields")
        projected_template = {
            key: value for key, value in template.items()
            if key in {"name", "document_type", "document", "modified", "creation"}
        }
        questions = configuration.get("assessment_questions", template.get("assessment_questions", []))
        projected_questions = [_project_question(row) for row in questions]
        sources = configuration.get("source_catalogue", {})
        projected_sources = {key: _project_source(value) for key, value in sorted(sources.items())}
        content: dict[str, bytes] = {
            "run_context.json": _canonical(run_context),
            "master_prompt.md": prompt.encode("utf-8"),
            "result_contract.json": contract.encode("utf-8"),
            "template_snapshot.json": _canonical(projected_template),
            "questions.json": _canonical(projected_questions),
            "source_catalogue.json": _canonical(projected_sources),
            "research_plan.json": _canonical(configuration.get("research_plan", {})),
            "organization_exclusions.json": _canonical(configuration.get("organization_exclusions", [])),
        }
        hashes = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(content.items())}
        manifest = {"package_schema_version": self.VERSION,
                    "template_name": template.get("name"),
                    "template_modified": template.get("modified"),
                    "source_identities": sorted(sources),
                    "source_counts": configuration.get("source_counts", {}),
                    "retrieval_metrics": configuration.get("retrieval_metrics", {}),
                    "files": sorted(content),
                    "creation_metadata": configuration.get("creation_metadata", {})}
        content["checksums.json"] = _canonical(hashes)
        content["manifest.json"] = _canonical(manifest)
        if output_dir is not None:
            target = Path(output_dir)
            target.mkdir(parents=True, exist_ok=False)
            for name, data in content.items():
                (target / name).write_bytes(data)
            archive = target / f"{target.name}.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipped:
                for name in sorted(content):
                    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    zipped.writestr(info, content[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            self.verify_archive(archive, content)
        return {"manifest": manifest, "checksums": hashes,
                "files": {name: data for name, data in content.items()}}

    @staticmethod
    def verify_archive(archive: str | Path, expected: dict[str, bytes]) -> None:
        with zipfile.ZipFile(archive) as zipped:
            if zipped.testzip() is not None:
                raise ValueError("Package ZIP failed its CRC integrity check")
            expected_names = set(expected)
            if set(zipped.namelist()) != expected_names:
                raise ValueError("Package ZIP entries do not match the package manifest")
            for name, payload in expected.items():
                if zipped.read(name) != payload:
                    raise ValueError(f"Package ZIP content mismatch for {name}")


def _project_question(row: dict[str, Any]) -> dict[str, Any]:
    fields = {"name", "assessment_category", "question", "weightage", "close_ended",
              "mandatory", "ai_prompt_instructions"}
    return {key: row[key] for key in fields if key in row}


def _project_source(source: dict[str, Any]) -> dict[str, Any]:
    result = {key: source.get(key) for key in ("name", "source_name", "url", "disabled")}
    for field, link in (("applicable_territories", "territory"),
                        ("applicable_assessment_categories", "assessment_category")):
        rows = source.get(field, [])
        result[field] = [{key: row[key] for key in ("name", link) if key in row}
                         for row in rows]
    return result
