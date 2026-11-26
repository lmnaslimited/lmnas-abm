# Research package schema (v2.0)

Package files are UTF-8. JSON uses sorted keys, compact separators, and a trailing newline. `master_prompt.md` is the current CRM `master_prompt` string encoded byte-for-byte; `result_contract.json` remains the exact CRM contract bytes. No CRM records are changed.

Each run creates `packages/<run-id>/` and places `<run-id>.zip` inside that same directory. The ZIP contains exactly the package files (without a nested directory prefix and without itself), with sorted relative paths and a fixed timestamp. Before returning, the writer checks ZIP CRC, entry names, and byte equality against the package content and manifest checksums.

| File | Contents |
|---|---|
| `manifest.json` | Schema version, template identity/version, complete source identities, source counts, request counts/errors/timings by DocType, file list, creation metadata. |
| `run_context.json` | Run scope, operation, stage, and identifiers. |
| `master_prompt.md` | Exact CRM master prompt. |
| `result_contract.json` | Exact CRM result contract. |
| `template_snapshot.json` | Projected template identity/configuration fields only. |
| `questions.json` | Ordered projected question identity, category, wording, weight, flags, and AI research instructions; excludes evaluation results and audit fields. |
| `source_catalogue.json` | Complete projected source catalogue, including disabled and out-of-scope sources, keyed by CRM identity. Retains source identity/name/URL/disabled and child row identities plus territory/category links. |
| `research_plan.json` | Exactly `global`, `regional`, and aggregated `regional_descendants` phases; source/category/question associations, explicit links, earliest-phase provenance, matching territory identities, and concise unassigned reasons. |
| `organization_exclusions.json` | Every CRM Organization, without territory filters, projected to CRM identity, organization name, and website URL. Missing websites remain null. |
| `checksums.json` | SHA-256 for each content file except manifest and checksums themselves. |

The current CRM Assessment Template embeds the question rows and their category Link identities, so one full template read supplies both. Categories are not fetched individually. The live Frappe API v2 list endpoint silently omits child tables on lookup-source rows even when child fields are requested. Preparation therefore paginates source identity/state, then reads each full source document once to preserve territory/category applicability. Organizations and CRM Territories are bulk paginated. `manifest.json` records measured request counts, failures, and elapsed seconds by DocType; the CLI reports retrieved counts and URL coverage.

Disabled lookup source masters remain in `source_catalogue.json` but are never assigned to the research plan. Every active source is either assigned or has a reason in `unassigned_sources`. A source is assigned once, at its earliest matching phase, while all matching territory/category associations remain provenance. Territory ancestry comes from `CRM Territory.parent_crm_territory`; nested set `lft` orders descendants.

Package assembly requires a new output directory and fails if one already exists. It does not overwrite earlier packages.
