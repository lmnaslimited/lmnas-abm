# CRM Read Integration

## Scope and safety

This milestone adds read-only CRM access through the Frappe CLI's `fr api`. It does not write, create, submit, update or delete CRM data. It does not use `fr doc get`. The CLI resolves credentials from its existing environment; the application never reads or logs credential values. Transport errors deliberately omit raw CLI output and stderr.

Implementation:

- `src/abm/crm/client.py` — subprocess transport, typed `-F` parameter encoding, JSON parsing, document reads and paginated list reads.
- `src/abm/crm/repository.py` — CRM-specific retrieval methods for Organizations, CREATE templates, UPDATE Assessments, linked categories, lookup sources and Organization reference lists.

The application must run where the configured `fr` executable and its site profile are available, currently the `lmnas-frappectl` container. The client calls `fr api` directly and inherits the process environment; it does not load secrets from files or print their values.

## Verified CLI and API syntax

In-container help reported:

```text
fr api [OPTIONS] {path}
Make a raw request to /api/v2/<path>.
-F, --field key=value (typed scalar) or key:=value (raw JSON), repeatable
-f, --raw-field key=value (always string), repeatable
-X, --method HTTP method; default GET unless params/input given
```

Read-only document retrieval uses the API v2 document routes:

```sh
fr api 'document/CRM%20Organization/BEZ%20Transform%C3%A1tory'
fr api -F 'fields:=["name"]' -F 'limit=5' -F 'start=5' 'document/Assessment%20Category'
```

A single-document response is a JSON object. A list response is a JSON array. Names and DocTypes are percent-encoded as URL path segments. `fields`, `filters`, `limit`, and `start` are sent as repeated `-F` arguments; arrays use the `:=` raw JSON form.

Live probing confirmed `limit` and `start` affect v2 document lists. The legacy-style `limit_page_length` and `limit_start` arguments did not limit or advance the result set in this CLI/API combination. The client uses `limit`/`start`, requests a stable `name` field in every page, and advances by the returned row count.

## Live verification performed

Commands ran inside `lmnas-frappectl` using the configured read context:

```sh
fr --version
fr api --help
fr doctype show 'CRM Organization'
fr doctype show 'CRM Assessment'
fr doctype show 'Assessment Template'
fr doctype show 'Assessment Questions'
fr doctype show 'Assessment Category'
fr doctype show 'Assessment Lookup Source'
fr doctype show 'Assessment Lookup Sources'
```

`fr api` GETs retrieved the live `CRM Organization` document `BEZ Transformátory`, Template `ASSTP-CRM Organization-01`, Assessment `CRM-ASS-00028`, linked Assessment Category documents, and Organization reference lists. The Organization response contained four `custom_assessment_summary` rows, including linked Assessment names. The Organization Template contained 17 embedded Assessment Questions rows and a string-valued `result_contract`. Its template-level `lookup_sources` array was empty. The existing Assessment contained 16 embedded Assessment Questions rows and referenced `ASSTP-CRM ProductLENS CPQ-01`. Its `reference_doctype`/`reference_document` were `CRM Organization` / `BEZ Transformátory`.

The repository was run inside the container and reported 8 distinct categories for the CREATE template, 7 for the UPDATE assessment, and 149 Currency, 18 CRM Territory and 30 CRM Industry values. These counts describe the result at verification time. No master-prompt body or long supporting-evidence fields were printed in that repository verification.

## Verified live schema

### CRM Organization

`CRM Organization` is a non-submittable standard DocType, autoname `field:organization_name`. Relevant live fields from `fr doctype show`:

| Field | Type | Options / relationship |
|---|---|---|
| `organization_name` | Data | Unique; document name is the Organization name |
| `no_of_employees` | Select | `1-10`, `11-50`, `51-200`, `201-500`, `501-1000`, `1000+` |
| `currency` | Link | Currency |
| `exchange_rate` | Float | — |
| `annual_revenue` | Currency | Currency field option references `currency` |
| `organization_logo` | Attach Image | — |
| `website` | Data | — |
| `company_description` | Small Text | — |
| `linkedin`, `twitter`, `facebook` | Data | — |
| `territory` | Link | CRM Territory |
| `industry` | Link | CRM Industry |
| `address` | Link | Address |
| `custom_account_manager` | Link | User |
| `custom_assessment_summary` | Table | CRM Assessment Summary child rows |

The repository fetches values for the verified `currency`, `territory`, and `industry` links by default. `get_organization_reference_data(additional_link_doctypes={...})` and `list_reference_documents()` allow a caller to retrieve metadata-confirmed extra targets such as Address or User on demand, avoiding an unrequested broad read of those records.

### Assessment Template

`Assessment Template` is non-submittable. Relevant fields:

| Field | Type | Options / relationship |
|---|---|---|
| `document_type` | Link | DocType |
| `naming_series` | Select | `ASSTP-.{document_type}.{document}.-.##` |
| `document` | Dynamic Link | Options field `document_type` |
| `assessment_questions` | Table | Assessment Questions |
| `master_prompt` | Text Editor | — |
| `lookup_sources` | Table MultiSelect | Assessment Lookup Sources (plural) |
| `result_contract` | Code | Present in live metadata and returned as a string by the API |

The live field is `result_contract`; this implementation does not rename it to `output_contract`. The Template API response embeds `assessment_questions` and `lookup_sources`. The Organization Template's returned `document` was null, which is preserved as CRM data rather than inferred.

### CRM Assessment

`CRM Assessment` is submittable and names are generated by `naming_series`. Relevant fields:

| Field | Type | Options / relationship |
|---|---|---|
| `document_type` | Link | DocType |
| `document` | Dynamic Link | Options field `document_type` |
| `assessment_template` | Link | Assessment Template |
| `amended_from` | Link | CRM Assessment |
| `reference_doctype` | Link | DocType |
| `reference_document` | Dynamic Link | Options field `reference_doctype` |
| `assessment_questions` | Table | Assessment Questions |
| `ai_score` | Float | — |
| `final_score` | Float | Read-only |

The live `CRM-ASS-00028` is an Organization-linked Product assessment: `document_type=CRM Product`, `document=LENS CPQ`, `reference_doctype=CRM Organization`, and `reference_document=BEZ Transformátory`. It contained 16 existing child rows. No mapping or writeback is performed by this milestone.

### Assessment Questions child DocType

`Assessment Questions` has `istable=1`; it is a child DocType, not a standalone record collection used by this repository. Rows are retrieved embedded through the parent Template or Assessment's `assessment_questions` field. Actual fields include:

- Identity/order/relationship: `name`, `idx`, `parent`, `parentfield`, `parenttype`.
- Question configuration: `assessment_category` (Link → Assessment Category, required), `question` (Small Text), `weightage` (Percent), `close_ended` (Check), `mandatory` (Check), `additional_lookup_sources` (Table MultiSelect → Assessment Lookup Sources), `ai_prompt_instructions` (Small Text).
- AI values: `ai_rating` (Rating), `ai_evidence_status` (Select: Supported / Inferred / Insufficient), `ai_confidence` (Select: Low / Medium / High), `ai_supporting_evidence` (Text Editor), `ai_score` (Float).
- Human/review values: `accept_ai` (Check), `evidence_status` (same three Select options), `rating` (Rating), `confidence` (same three Select options), `supporting_evidence` (Text Editor), `score` (Float, read-only).

The same child DocType is used under a Template and a CRM Assessment. The template child-row `name` and existing Assessment child-row `name` are both returned by the API; they are distinct row identities in the observed records. This milestone only retrieves them and does not map or copy IDs.

### Assessment Category

`Assessment Category` is a standard non-submittable DocType, autoname `field:category_name`. Fields:

- `category_name` (Data)
- `description` (Small Text)
- `disabled` (Check)
- `applicable_document_type` (Link → DocType)
- `applicable_document` (Dynamic Link, options field `applicable_document_type`)

Question rows link to category records through `assessment_category`. The repository de-duplicates those names and reads each category through `document/Assessment%20Category/{name}`.

### Assessment Lookup Source master and Assessment Lookup Sources child table

These are distinct DocTypes with different retrieval rules:

- `Assessment Lookup Source` (singular) is the master DocType with `source_name` (unique Data), `url` (Data), and `disabled` (Check). A master is fetched independently by its linked document name only when a parent row references it. The complete master document is retained in `lookup_source_records`, making its URL and other metadata available to consumers.
- `Assessment Lookup Sources` (plural) is a child DocType (`istable=1`) with `lookup_source` (required Link → Assessment Lookup Source). Its rows are read only as embedded values through `Assessment Template.lookup_sources` or `Assessment Questions.additional_lookup_sources`. The code never lists or gets this child DocType as a standalone document.

A lookup association entry retains its original location, parent question row identity/order where applicable, child-row `name` and `idx`, link value, and the original child-row object. Associations remain separate from `lookup_source_records`, which are deduplicated by master name. No embedded child row is replaced by a master record.

Permission verification: a direct list request for the plural child DocType still returned `Insufficient Permission`; that standalone request is not part of the implementation and will not be retried. The last `fr doctype show` metadata also showed read permission for the singular master only on System Manager; a list request through the configured principal returned an empty array. Because no parent currently references a master name, an individual master GET/URL read could not be exercised live. All six live Assessment Templates were read through the parent API; none has template-level or question-level lookup links, so there are no live referenced master names to fetch or URLs to demonstrate against CRM data in this pass. Selective master resolution, including URL availability, is covered with mocked API responses. When a reference exists, only those distinct singular master documents are fetched. A missing/unreadable master, missing link value, mismatched master identity, missing `source_name`, or empty/missing URL raises `CRMReadContextError` rather than silently dropping the source.

## Consolidated read contexts

`prepare_create_read_context(template_name, organization_name=None, include_organization_reference_data=None)` returns a `CreateReadContext` with:

- The selected full `assessment_template` and its unchanged embedded `assessment_questions` list.
- `question_category_links` keyed to each question `name`/`idx`, plus a deduplicated `assessment_categories` map.
- Original template- and question-level lookup child rows represented in order by `lookup_source_links`; separately deduplicated referenced master documents in `lookup_source_records`.
- The selected existing `organization` when provided.
- CRM Organization reference lists when applicable (by default for an Organization template), with an explicit override for callers.

`prepare_update_read_context(assessment_name, include_organization_reference_data=None)` returns an `UpdateReadContext` with:

- The selected existing `assessment` and its unchanged embedded question rows as the authoritative question set.
- The linked `assessment_template_name` and only its embedded template-level `lookup_sources` rows. The template's question rows are not used to replace or augment the Assessment's question set.
- Category links/maps for the Assessment question rows.
- Lookup associations from the linked Template's template-level rows and the existing Assessment's question-level rows. Referenced singular masters are fetched once each.
- The associated Organization and its reference lists when the Assessment's live relationship points to a CRM Organization.

For both contexts, child rows remain distinct and retain their `name`, `idx`, link values and other properties. Master records remain separately keyed by master document name, so URLs are available as `context.lookup_source_records[lookup_source_name]["url"]` without erasing child-row identity. Calls are made only for referenced categories/sources and applicable Organization/reference data. No standalone request is made for `Assessment Lookup Sources`.

The lower-level `get_assessment_template_for_create`, `get_assessment_for_update`, `get_assessment_categories`, `get_lookup_sources_for_template`, and generic reference list methods remain available. Raw stderr/stdout is withheld on API failures to prevent credential leakage; transport errors expose only a sanitized message/exit code, and context failures identify the referenced CRM document without printing server diagnostics.

No draft duplicate detection, workflow eligibility checks, approval, CRM writes, prompt assembly or agent integration are included. CRM access and schema can change; live metadata remains authoritative.

## Tests

Mocked tests exercise CLI argument construction, encoded document paths, response decoding, list pagination, sanitized failures, CREATE/UPDATE read contexts, embedded lookup rows, selective/deduplicated singular master retrieval, URL availability, missing/incomplete master handling, category identity links, and Organization reference retrieval. They do not contact production CRM.

Run with:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```
