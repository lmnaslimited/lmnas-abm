"""Territory- and category-aware lookup source planning."""

from __future__ import annotations

from typing import Any


class SourceResolutionError(ValueError):
    pass


SOURCE_CHILD_LINKS = {"territor": ("applicable_territories", "territory"),
                      "categor": ("applicable_assessment_categories", "assessment_category")}


def _links(source: dict[str, Any], keyword: str) -> list[str]:
    field, link = SOURCE_CHILD_LINKS[keyword]
    if not isinstance(source.get(field), list):
        raise SourceResolutionError(f"Source {source.get('name')!r} has invalid {keyword} rows")
    result = []
    for row in source[field]:
        if not isinstance(row, dict) or not isinstance(row.get(link), str) or not row[link]:
            raise SourceResolutionError(f"Source {source.get('name')!r} has invalid {keyword} reference")
        result.append(row[link])
    return result


def _territory_tree(territories: dict[str, dict[str, Any]]) -> dict[str, str | None]:
    parents = {}
    for name, doc in territories.items():
        # Tree relationship is read from the CRM's actual parent field.
        parent = doc.get("parent_crm_territory")
        parents[name] = parent or None
    for name, parent in parents.items():
        if parent is not None and parent not in parents:
            raise SourceResolutionError(f"Territory {name!r} references unknown parent {parent!r}")
    for start in parents:
        visited = set()
        node: str | None = start
        while node:
            if node in visited:
                raise SourceResolutionError(f"Territory tree contains a cycle at {node!r}")
            visited.add(node)
            node = parents[node]
    return parents


def resolve_sources(
    catalogue: dict[str, dict[str, Any]], territories: dict[str, dict[str, Any]], *,
    run_territory: str | None, scope_type: str, questions: list[dict[str, Any]],
    explicit_links: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build ordered territory phases and category/question source associations."""
    parents = _territory_tree(territories)
    if run_territory and run_territory not in parents:
        raise SourceResolutionError(f"Unknown run territory {run_territory!r}")
    descendants: list[str] = []
    if run_territory:
        for candidate in parents:
            node: str | None = candidate
            while node and node != run_territory:
                node = parents[node]
            if node == run_territory and candidate != run_territory:
                descendants.append(candidate)
    if any(not isinstance(territories[n].get("lft"), (int, float)) for n in descendants):
        raise SourceResolutionError("CRM Territory documents must include numeric lft ordering metadata")
    descendants.sort(key=lambda n: (territories[n]["lft"], n))
    parent = parents.get(run_territory) if run_territory else None
    if scope_type == "region":
        territory_phases = [("global", None), ("regional", run_territory),
                             ("regional_descendants", descendants)]
    elif scope_type == "country":
        territory_phases = [("exact", run_territory), ("parent", parent), ("global", None)]
    else:
        raise SourceResolutionError("scope_type must be 'region' or 'country'")

    source_territories = {name: _links(doc, "territor") for name, doc in catalogue.items()}
    source_categories = {name: _links(doc, "categor") for name, doc in catalogue.items()}
    phase_sources: list[dict[str, Any]] = []
    chosen_phase: dict[str, int] = {}
    for i, (phase, territory) in enumerate(territory_phases):
        rows = []
        for source_id, doc in catalogue.items():
            assigned = source_territories[source_id]
            matches = (not assigned and territory is None) or (
                territory is not None and
                (territory in assigned if isinstance(territory, str)
                 else any(item in assigned for item in territory))
            )
            if scope_type == "country" and phase == "parent":
                matches = bool(assigned) and parent in assigned
            if scope_type == "country" and territory is None:
                matches = not assigned
            if matches and source_id not in chosen_phase:
                chosen_phase[source_id] = i
                rows.append(source_id)
        phase_sources.append({"phase": phase, "territory": territory, "source_ids": rows})
    # Category applicability is independent of territory. Explicit links bypass
    # automatic category matching but never bypass the territory plan.
    question_sources: dict[str, list[str]] = {}
    explicit_template = []
    explicit_question: dict[str, list[str]] = {}
    explicit_by_source: dict[str, list[dict[str, Any]]] = {}
    for link in explicit_links or []:
        sid = link["lookup_source"]
        explicit_by_source.setdefault(sid, []).append(link)
        if link["location"] == "template.lookup_sources":
            explicit_template.append(sid)
        else:
            explicit_question.setdefault(link["question_row_name"], []).append(sid)
    generic: list[str] = []
    category_map: dict[str, list[str]] = {}
    for phase in phase_sources:
        phase["generic_source_ids"] = []
        phase["category_sources"] = {}
        for sid in phase["source_ids"]:
            cats = source_categories[sid]
            if not cats:
                generic.append(sid)
                phase["generic_source_ids"].append(sid)
            else:
                for cat in cats:
                    category_map.setdefault(cat, []).append(sid)
                    phase["category_sources"].setdefault(cat, []).append(sid)
    eligible = set(chosen_phase)
    for question in questions:
        qid = question.get("name")
        cat = question.get("assessment_category")
        selected = list(dict.fromkeys(
            [sid for sid in explicit_question.get(qid, []) + explicit_template if sid in eligible]
            + category_map.get(cat, [])
        ))
        question_sources[str(qid)] = selected
    reasons = {}
    explicit = set(explicit_template + [s for values in explicit_question.values() for s in values])
    question_categories = {str(row.get("name")): row.get("assessment_category") for row in questions}
    for sid in catalogue:
        matching_territories = source_territories[sid]
        if sid in explicit:
            reason = "explicit_template" if sid in explicit_template else "explicit_question"
        elif not source_categories[sid]:
            reason = "generic"
        else:
            reason = "category_match"
        rationale = [f"explicit:{link['location']}" for link in explicit_by_source.get(sid, [])]
        rationale.append("category_match" if source_categories[sid] else "generic_research")
        applicable = sid in chosen_phase
        if not applicable:
            rationale.append("territory_not_applicable")
        reasons[sid] = {"priority": (0 if sid in explicit else 1) if applicable else None,
                        "territory_applicable": applicable, "reason": reason,
                        "selection_reasons": list(dict.fromkeys(rationale)),
                        "applicable_territories": matching_territories,
                        "applicable_categories": source_categories[sid],
                        "matching_territories": [
                            territory for territory in matching_territories
                            if territory in descendants or territory == run_territory
                        ],
                        "phase_index": chosen_phase.get(sid)}
    return {"run_territory": run_territory, "scope_type": scope_type,
            "phases": phase_sources, "generic_source_ids": list(dict.fromkeys(generic)),
            "category_sources": category_map, "question_sources": question_sources,
            "question_categories": question_categories,
            "template_explicit_source_ids": list(dict.fromkeys(explicit_template)),
            "question_explicit_source_ids": explicit_question,
            "explicit_associations": list(explicit_links or []),
            "source_selection": reasons}
