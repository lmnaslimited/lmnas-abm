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

### Assessment Lookup Source and its multiselect child table

Live metadata distinguishes two DocTypes:

- `Assessment Lookup Source` is a standard DocType with `source_name` (unique Data), `url` (Data), and `disabled` (Check). Its read permission is granted to System Manager only.
- `Assessment Lookup Sources` (plural) is a child DocType (`istable=1`) with `lookup_source` (required Link → Assessment Lookup Source) and no DocType-level permissions listed.

Both Template `lookup_sources` and question `additional_lookup_sources` are Table MultiSelect fields targeting the plural child DocType. A later permission recheck found that API listing of the plural child table `Assessment Lookup Sources` still returns `Insufficient Permission` for the configured user. Listing the singular `Assessment Lookup Source` DocType succeeds but currently returns an empty list. All six live Assessment Templates were read, and each has zero template-level and question-level lookup links, so no source record currently needs to be resolved. If a later configuration contains source references, repository retrieval attempts the singular linked records and fails closed with a sanitized `FrappeAPIError`; it does not silently omit inaccessible sources.

## Retrieval behavior and limitations

- CREATE preparation calls `get_assessment_template_for_create(template_name)` and receives the template's authoritative `assessment_questions` rows, including row IDs and linked category names.
- UPDATE preparation calls `get_assessment_for_update(assessment_name)` and receives the selected existing Assessment's own `assessment_questions`, not the current template's question set.
- `get_assessment_categories(question_rows)` fetches distinct linked categories. `get_lookup_sources_for_template(template)` resolves referenced multiselect values when permissions allow.
- Organization mapping lists Currency, CRM Territory and CRM Industry. Additional verified Link targets can be requested as needed.
- Read errors and malformed payloads raise `FrappeAPIError`. Raw stderr/stdout is intentionally withheld to prevent credential leakage; the current error includes only a generic failure and CLI exit status.
- The configured user can list the singular `Assessment Lookup Source` DocType, which returned no rows, but cannot directly list `Assessment Lookup Sources` child rows. No linked source rows exist on the six live Templates at verification time, so successful retrieval of a populated multiselect remains unverified. CRM access and schema can change; live metadata remains authoritative.
- No draft duplicate detection, workflow eligibility checks, approval, CRM writes, prompt assembly or agent integration are included.

## Tests

Mocked tests exercise CLI argument construction, encoded document paths, response decoding, list pagination, sanitized failures, CRM Template/Assessment retrieval, child rows, linked-category de-duplication, lookup handling and Organization reference retrieval. They do not contact production CRM.

Run with:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```
