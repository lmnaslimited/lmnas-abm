# Reuse and migration map

| Capability | Source of truth now | Consolidation approach |
|---|---|---|
| Discovery, ICP, deduplication, dispositions | `lmnas_discovery_pipeline/src/{pipeline,quality,decisions,history}.py` and SQLite | Wrap the CLI and preserve the existing DB and manifest formats. Do not fork the discovery history. |
| CRM organization import | `lmnas_discovery_pipeline/src/crm_import.py` | Reuse after validating safeguards; the older organization importer is reference-only. |
| Organization/product assessments | `lmnas-crm-research-orchestrator/src/orchestrator.py`, templates supplied by CRM/package | Wrap its exact existing package/writeback behavior. Never clone weights/questions into ABM config. |
| Assessment research queue/prompt | `lmnas_crm_research_engine` | Integrate as an independent callable stage, preserve prompts and JSON formats. |
| CRM client | Existing separate `fr api` wrappers | Extract one shared client only after comparing semantics and executing it inside Docker; preserve API response/error behavior and redact secrets. |
| Financial normalization | No common service found | Audit shows competing conventions and suspicious data; specify one `Decimal` service in Phase 2 and migrate only with fixtures and source provenance. |
| Contact research and Contact/Lead sync | No implementation found in scanned code | New bounded module. It must retrieve live Lead and Contact metadata before field mapping; fail closed without metadata. One person key, one Contact and normally one Lead with multi-product interests. Dry-run and approval controls match Organization sync. |
| Workflow/reporting | Discovery manifests/history and assessment package manifests | Add thin coordinator and consolidated report that reference existing artifacts rather than copy them. Track per-stage status and CRM IDs; retry by searching before create. |

## Implemented reuse map

The shared assessment engine in `src/abm/assessment/engine.py` dynamically loads the existing orchestrator source and delegates these exact functions:

| Existing function | Shared engine operation |
|---|---|
| `assessment_config()` | Load configured assessment templates/labels/folders from `config/assessment_types.json`. |
| `get_assessments(org_id, org)` | Resolve the four current CRM Assessment records using linked summary then the existing filtered-list fallback; enforce identity, Draft status, and unique child IDs. |
| `prepare(org_id, dry_run)` | Build the established research package, manifest, exact question snapshots, prompts, rating convention and schemas. |
| `validate_result(org_id, aid, meta, result)` | Validate identity, template, exact question set, rating, evidence IDs, status and narrative structure. |
| `collect(org_id, package_id, result_zip)` | Safely unpack, validate and stage results; CRM is unchanged. |
| `apply(org_id, package_id, confirm, dry_run)` | Revalidate, preflight every existing Draft record, then update the four AI fields and record source receipt. |

Discovery wraps `src/pipeline.py` via `prepare`, preserving `quality.validate_candidate`, `decisions.disposition`, `history.upsert`, run manifests, and `crm_import.import_candidate` behavior. ABM does not modify those projects. The discovery code has a separate internal `fr_api` helper today; a full shared-client migration is deferred until behavior can be compared inside Docker. The new ABM assessment and contact reads use a single `abm.crm.client` adapter. Product assessments are not yet resolved by the engine because the existing orchestrator resolver is organization-only and CRM metadata/identity rules were inaccessible.

Original projects are untouched by this implementation; all edits are in `workspace/lmnas-abm`.

## Interrupted attempt inventory

The prior interrupted turn created `workspace/lmnas-abm/pyproject.toml`, `src/abm/__init__.py`, empty `contacts` and `crm` package markers, and `src/abm/crm/client.py`. The client duplicates the existing `fr` wrapper before the Docker runtime was inspected and has a guessed `doctype/...` metadata endpoint. Do not treat that endpoint or package design as validated. No existing project was modified. In Phase 2 either adapt or remove this duplicate only after verifying the existing implementations and live API.
