# Research package schema (v1.0)

Package files are UTF-8. JSON files use sorted keys, compact separators and a trailing newline. `master_prompt.md` is the CRM `master_prompt` string encoded as UTF-8 without edits. `result_contract.json` contains the exact CRM `result_contract` string, byte-for-byte.

| File | Contents |
|---|---|
| `manifest.json` | Schema version, CRM template identity/version metadata, source identities, content file list, optional caller-supplied creation metadata. |
| `run_context.json` | Caller-provided run scope and identifiers. |
| `master_prompt.md` | Unchanged CRM master prompt. |
| `result_contract.json` | Unchanged CRM result contract. |
| `template_snapshot.json` | Complete CRM template document including embedded rows. |
| `questions.json` | Ordered authoritative question rows. |
| `organization_context.json` | Present when the read context contains an Organization. |
| `source_catalogue.json` | Complete enabled source master documents keyed by CRM name. |
| `research_plan.json` | Run scope; ordered territorial phases with phase-specific generic/category pools; question-to-category/source mappings; template/question explicit associations including original child-row identity/order; source priority, rationale, applicable CRM territory/category identities and earliest-phase provenance. |
| `checksums.json` | SHA-256 of each content file except manifest and checksums themselves. |

Package assembly is deterministic for identical CRM and run inputs. Optional `creation_metadata` is caller-controlled. Disk assembly requires a new output directory and fails if that directory already exists, so package contents cannot be overwritten by a later assembly call.

The live CRM source master fields are `applicable_territories` (rows in `Territories`, link field `territory`) and `applicable_assessment_categories` (rows in `Assessment Categories`, link field `assessment_category`). Each row's full original CRM properties remain in `source_catalogue.json`. Territory ancestry comes from `CRM Territory.parent_crm_territory`; nested set `lft` order sorts descendants.

`ResearchPackagePreparer.prepare_create()` composes the CRM context, full enabled source catalogue, full territory list, explicit associations, source resolver and assembler. It does not invoke an agent or expose a country-run CLI command.
