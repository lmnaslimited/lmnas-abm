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
            template_name, organization_name=organization_name,
            include_organization_reference_data=False,
        )
        catalogue = self.repository.get_source_catalogue()
        organizations = self.repository.list_documents(
            "CRM Organization", fields=("name", "organization_name", "website")
        )
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
        source_pool = {
            key: value for key, value in catalogue.items()
            if str(value.get("disabled", "0")).lower() not in {"1", "true", "yes"}
        }
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
        selected_catalogue = {key: catalogue[key] for key in sorted(catalogue)}
        # Keep no references to out-of-scope catalogue records in the plan.
        plan["source_selection"] = dict(plan["source_selection"])
        plan["explicit_associations"] = [link for link in plan["explicit_associations"]]
        plan["unassigned_sources"] = {
            sid: ("disabled" if str(catalogue[sid].get("disabled", "0")).lower() in {"1", "true", "yes"}
                  else "territory_not_applicable")
            for sid in sorted(set(catalogue) - applicable_ids)
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
            "organization_exclusions": _project_organizations(organizations),
            "source_counts": {
                "retrieved": len(catalogue), "active": len(source_pool),
                "assigned": len(applicable_ids), "unassigned": len(source_pool) - len(applicable_ids),
                "with_url": sum(bool(str(s.get("url") or "").strip()) for s in catalogue.values()),
                "applicable_url_coverage": sum(
                    bool(str(catalogue[sid].get("url") or "").strip()) for sid in applicable_ids
                ),
            },
            "retrieval_metrics": _request_metrics(self.repository),
            "creation_metadata": run_context.get("creation_metadata", {}),
        }
        package = self.assembler.assemble(configuration, resolved_context, output_dir=output_dir)
        package["preparation_summary"] = {
            "catalogue_retrieved": len(catalogue),
            "applicable_selected": len(applicable_ids),
            "excluded": len(source_pool) - len(applicable_ids),
            "organizations_retrieved": len(organizations),
            "organization_exclusions": len(configuration["organization_exclusions"]),
            "phase_counts": [
                {"phase": phase["phase"], "territory": phase["territory"],
                 "source_count": len(phase["source_ids"])}
                for phase in plan["phases"]
            ],
        }
        return package


def _project_organizations(rows: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    result: dict[str, dict[str, str | None]] = {}
    for row in rows:
        identity = row.get("name")
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError("CRM Organization list contains a row without a stable name")
        value = {"crm_organization_id": identity,
                 "organization_name": row.get("organization_name") or identity,
                 "url": row.get("website") or None}
        previous = result.get(identity)
        if previous is not None and previous != value:
            raise ValueError(f"CRM Organization list contains conflicting duplicate {identity!r}")
        result[identity] = value
    return [result[key] for key in sorted(result)]


def _request_metrics(repository: Any) -> dict[str, Any]:
    api = getattr(repository, "api", None)
    if api is None or type(api).__name__ == "Mock":
        return {}
    method = getattr(api, "metrics_snapshot", None)
    return method() if callable(method) else {}


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
