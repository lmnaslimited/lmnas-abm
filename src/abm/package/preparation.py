"""Compose CRM read contexts, source resolution and immutable package assembly."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from abm.crm.repository import CRMRepository
from abm.package.assembler import PackageAssembler
from abm.package.source_resolver import resolve_sources


class ResearchPackagePreparer:
    def __init__(self, repository: CRMRepository | None = None,
                 assembler: PackageAssembler | None = None) -> None:
        self.repository = repository or CRMRepository()
        self.assembler = assembler or PackageAssembler()

    def prepare_create(
        self, template_name: str, run_context: dict[str, Any], *,
        run_territory: str, scope_type: str = "region",
        organization_name: str | None = None, output_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        """Assemble an Organization or other CREATE package from live CRM inputs."""
        context = self.repository.prepare_create_read_context(
            template_name, organization_name=organization_name
        )
        catalogue = self.repository.get_source_catalogue()
        territories_list = self.repository.list_documents(
            "CRM Territory",
            fields=("name", "parent_crm_territory", "lft", "rgt", "is_group"),
        )
        territories: dict[str, dict[str, Any]] = {}
        for row in territories_list:
            name = row.get("name")
            if not isinstance(name, str) or not name or name in territories:
                raise ValueError("CRM Territory catalogue contains a missing or duplicate identity")
            territories[name] = row

        explicit_ids = {row["lookup_source"] for row in context.lookup_source_links}
        explicit_sources = context.lookup_source_records
        missing = explicit_ids - set(explicit_sources)
        if missing:
            raise ValueError(f"Explicit CRM lookup sources could not be resolved: {sorted(missing)!r}")
        # Disabled explicit sources fail in repository context loading. Every
        # other explicit source must also remain territory-applicable.
        source_pool = dict(catalogue)
        for source_id in explicit_ids:
            if source_id not in source_pool:
                source_pool[source_id] = explicit_sources[source_id]
        plan = resolve_sources(
            source_pool, territories,
            run_territory=run_territory, scope_type=scope_type,
            questions=context.assessment_questions,
            explicit_links=context.lookup_source_links,
        )
        resolved_context = dict(run_context)
        resolved_context["run_territory"] = run_territory
        resolved_context["scope_type"] = scope_type
        configuration = {
            "assessment_template": context.assessment_template,
            "assessment_questions": context.assessment_questions,
            "organization": context.organization,
            "source_catalogue": source_pool,
            "research_plan": plan,
            "creation_metadata": run_context.get("creation_metadata", {}),
        }
        return self.assembler.assemble(configuration, resolved_context, output_dir=output_dir)
