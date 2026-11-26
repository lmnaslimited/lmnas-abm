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

        selected_territory = territories.get(run_territory)
        if selected_territory is None:
            raise ValueError(f"CRM Territory {run_territory!r} does not exist")
        if str(selected_territory.get("is_group", "0")).lower() not in {"1", "true", "yes"}:
            raise ValueError(f"CRM Territory {run_territory!r} is not a regional parent territory")

        explicit_ids = {row["lookup_source"] for row in context.lookup_source_links}
        explicit_sources = context.lookup_source_records
        missing = explicit_ids - set(explicit_sources)
        if missing:
            raise ValueError(f"Explicit CRM lookup sources could not be resolved: {sorted(missing)!r}")
        not_catalogued = explicit_ids - set(catalogue)
        if not_catalogued:
            raise ValueError(
                "Explicit lookup source(s) are absent from the enabled source catalogue: "
                f"{sorted(not_catalogued)!r}"
            )
        # The full catalogue is an internal resolver input. Only selected
        # masters are serialized into this regional package.
        source_pool = dict(catalogue)
        plan = resolve_sources(
            source_pool, territories,
            run_territory=run_territory, scope_type=scope_type,
            questions=context.assessment_questions,
            explicit_links=context.lookup_source_links,
        )
        applicable_ids = {
            source_id for phase in plan["phases"] for source_id in phase["source_ids"]
        }
        inapplicable_explicit = explicit_ids - applicable_ids
        if inapplicable_explicit:
            raise ValueError(
                "Explicit lookup source(s) are outside the selected regional territory scope: "
                f"{sorted(inapplicable_explicit)!r}"
            )
        selected_catalogue = {key: catalogue[key] for key in sorted(applicable_ids)}
        # Keep no references to out-of-scope catalogue records in the plan.
        plan["source_selection"] = {
            key: plan["source_selection"][key] for key in sorted(applicable_ids)
        }
        plan["explicit_associations"] = [
            link for link in plan["explicit_associations"]
            if link["lookup_source"] in applicable_ids
        ]
        plan["template_explicit_source_ids"] = [
            sid for sid in plan["template_explicit_source_ids"] if sid in applicable_ids
        ]
        plan["question_explicit_source_ids"] = {
            question: [sid for sid in ids if sid in applicable_ids]
            for question, ids in plan["question_explicit_source_ids"].items()
        }
        # Fail closed if a future plan field accidentally points outside the
        # exact master documents that will be packaged.
        _validate_plan_catalogue_consistency(plan, selected_catalogue)
        resolved_context = dict(run_context)
        resolved_context["run_territory"] = run_territory
        resolved_context["scope_type"] = scope_type
        configuration = {
            "assessment_template": context.assessment_template,
            "assessment_questions": context.assessment_questions,
            "organization": context.organization,
            "source_catalogue": selected_catalogue,
            "research_plan": plan,
            "creation_metadata": run_context.get("creation_metadata", {}),
        }
        package = self.assembler.assemble(configuration, resolved_context, output_dir=output_dir)
        package["preparation_summary"] = {
            "catalogue_retrieved": len(catalogue),
            "applicable_selected": len(selected_catalogue),
            "excluded": len(catalogue) - len(selected_catalogue),
            "phase_counts": [
                {"phase": phase["phase"], "territory": phase["territory"],
                 "source_count": len(phase["source_ids"])}
                for phase in plan["phases"]
            ],
        }
        return package


def _validate_plan_catalogue_consistency(
    plan: dict[str, Any], source_catalogue: dict[str, dict[str, Any]]
) -> None:
    source_ids = set(source_catalogue)
    references: set[str] = set()
    for phase in plan["phases"]:
        references.update(phase["source_ids"])
        references.update(phase["generic_source_ids"])
        for ids in phase["category_sources"].values():
            references.update(ids)
    references.update(plan["generic_source_ids"])
    for ids in plan["category_sources"].values():
        references.update(ids)
    for ids in plan["question_sources"].values():
        references.update(ids)
    references.update(plan["template_explicit_source_ids"])
    for ids in plan["question_explicit_source_ids"].values():
        references.update(ids)
    references.update(link["lookup_source"] for link in plan["explicit_associations"])
    references.update(plan["source_selection"])
    missing = references - source_ids
    if missing:
        raise ValueError(f"Research plan references sources absent from its package catalogue: {sorted(missing)!r}")
