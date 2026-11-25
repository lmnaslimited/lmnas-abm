# LMNAs ABM Architecture

**Status:** Initial implementation baseline
**Architecture approach:** Clean implementation
**Primary responsibility:** CRM-driven Account-Based Marketing research orchestration
**System of record:** LMNAs CRM
**Research execution:** External research agent, supplied with an immutable execution package

## 1. Purpose

Build a clean, generic ABM application that orchestrates research and assessment workflows using CRM configuration.

The ABM application is a **package assembler, execution manager, validation layer and CRM integration layer**. It is not a prompt generator, assessment-question generator, replacement for CRM, hardcoded industry-specific assessment engine, or direct CRM-writing research agent.

The application retrieves authoritative configuration from CRM, assembles a research package, invokes a research agent, validates its output and manages the resulting assessment workflow.

## 2. Core design principles

1. **CRM is the source of truth.** Assessment templates, questions, master prompts, output contracts, lookup sources and CRM reference values originate in CRM.
2. **Configuration over code.** Business-specific questions, scoring rules, mandatory criteria and research instructions are supplied through CRM configuration and run context.
3. **No prompt construction.** ABM retrieves and packages the master prompt unchanged. It must not generate, append, rewrite or dynamically inject prompt instructions.
4. **One assessment model.** Discovery, full assessment, product assessment and reassessment all produce assessment question results.
5. **Explicit assessment operation.** `CREATE` and `UPDATE` are command-level flags independent of research stage.
6. **Explicit question identity.** The agent returns the question identifiers supplied in the package. ABM controls how those identifiers map to CRM rows.
7. **Human ownership is preserved.** AI must never overwrite human assessment fields.
8. **No premature CRM writes.** Results are staged and validated before human confirmation and CRM persistence.
9. **Auditable execution.** Every run retains its package, outputs, validation results, decisions and execution history.
10. **Provider independence.** Research-agent invocation is isolated behind an adapter.
11. **Fail closed.** Invalid configuration, output, ambiguous mapping, duplicate draft assessments or failed authorization stop the operation.
12. **Clean implementation.** The new runtime has no dependency on the legacy branch's architecture or runtime dependencies.

## 3. Functional model

### 3.1 Assessment operation

The command requires an explicit `assessment_operation`:

- `CREATE`
- `UPDATE`

This is a command-level input, not an Assessment Template field. The operation determines the authoritative question source and CRM persistence behavior.

| Operation | Question source | Question identifier | CRM behavior |
|---|---|---|---|
| CREATE | Assessment Template | Template child-row ID | Create new Assessment child rows |
| UPDATE | Existing CRM Assessment | Existing Assessment child-row ID | Update AI fields on matching existing rows |

For CREATE, template child-row IDs are correlation IDs only. CRM assigns new child-row identities. For UPDATE, existing Assessment and child-row identities remain unchanged.

### 3.2 Research stage

Research stage is independent of operation. Supported stages are `DISCOVERY` and `FULL_ASSESSMENT`. The command explicitly supplies the operation; the workflow validates supported combinations.

### 3.3 Supported scenarios

| Scenario | Operation | Stage | Question source |
|---|---|---|---|
| Discover new Organizations | CREATE | DISCOVERY | Organization Assessment Template |
| Complete an Organization assessment | CREATE | FULL_ASSESSMENT | Organization Assessment Template |
| Create a Product Assessment for an existing Organization | CREATE | FULL_ASSESSMENT | Product Assessment Template |
| Reassess an Organization | UPDATE | FULL_ASSESSMENT | Existing Organization Assessment |
| Reassess a Product | UPDATE | FULL_ASSESSMENT | Existing Product Assessment |

## 4. CRM integration and ownership

Live CRM metadata must be inspected before assuming DocTypes, fields, relationships, workflow states, allowed values or permissions. Templates provide target DocType, question rows and IDs, categories, wording, type, weightage, flags, question instructions, lookup sources, master prompt and output contract. For UPDATE, the existing Assessment and its actual question rows are authoritative; the current template must not replace them.

AI-controlled fields are `ai_rating`, `ai_evidence_status`, `ai_confidence` and `ai_supporting_evidence`. Human-controlled fields are `rating`, `evidence_status`, `confidence`, `supporting_evidence`, `accept_ai`, `score`, `final_score` and `docstatus`. Actual field metadata must be confirmed. AI writeback never modifies human-owned fields, including when empty.

## 5. Command interface

The CLI requires an explicit assessment operation, conceptually:

```text
abm run --assessment-operation CREATE ...
abm run --assessment-operation UPDATE ...
```

The operation is never inferred from an Assessment ID. CREATE and UPDATE require the applicable template or existing Assessment inputs, target, stage, run context and agent configuration.

## 6. Validation and duplicate protection

CREATE performs a duplicate preflight before research and repeats the relevant check before CRM persistence. A matching draft Assessment for the same target and context blocks the operation with a clear conflict; it never silently switches to UPDATE or partially creates records. The exact matching context must follow live CRM relationships and workflow metadata. UPDATE verifies that the Assessment exists and is eligible for reassessment.

Agent output is validated against the exact CRM-supplied contract and authoritative question source. Missing, duplicate, unknown or reordered IDs, changed question metadata, invalid values, unsupported evidence references and malformed output fail closed. Discovery qualification uses configured thresholds and scoring rules; insufficient evidence requires review. Organization fields and Link values are validated against live metadata/reference data with field-level evidence.

## 7. Research package and agent boundary

The package includes applicable artifacts such as byte-for-byte copies of `master_prompt.md` and `output_contract.json`, run context, template or existing Assessment snapshot, research sources, CRM reference data, exclusions, account context and known Organization data. A manifest records source identifiers, versions, checksums and creation metadata. Package contents are immutable for a run.

Sources combine template, question and run-specific lookup sources; they are starting points, and the agent cites sources actually used. A provider-neutral adapter receives the package, invokes the configured agent, tracks status and returns complete raw response and execution metadata. It does not modify prompts/contracts/questions, map CRM records, write CRM data or approve results.

## 8. Output validation

Parse and validate output against the exact supplied contract. Validate one result per expected question, with unchanged IDs, wording, category, type, flags and sequence; validate ratings against live CRM semantics and verify evidence. Do not repair missing data or fabricate answers. Discovery dispositions, threshold rules, mandatory negative findings and insufficient-evidence review are validated using configured rules. Organization payloads are checked against live metadata and reference data; every non-null proposed field needs evidence, and identifiers are never invented.

## 9. Workflow: Prepare → Collect → Confirm

**Prepare:** validate command, retrieve configuration, resolve question source, run preflight checks, assemble immutable package and record run metadata.

**Collect:** submit package, capture raw response, validate output, stage results and preserve errors/limitations. No final CRM writes occur before confirmation.

**Confirm:** present findings and evidence for human review; record approval, rejection or further research; on approval, persist using actual CRM workflow states and permissions. Record CRM references and audit trail.

## 10. CRM persistence

For CREATE Organization discovery, after approval revalidate identity and draft conflicts, create the approved Organization and linked Assessment, map template correlation IDs to newly created child rows, write AI fields only, preserve human fields and use an atomic transaction or safe compensation where supported. Avoid orphan Organizations or partial Assessments.

For CREATE on an existing target, validate target and context, reject conflicting drafts, create a new Assessment and child rows, map correlation IDs and persist AI fields.

For UPDATE, validate Assessment, target and workflow eligibility; map results to existing rows and update AI-controlled fields only. Preserve Assessment and row IDs, human fields and reassessment history.

## 11. Discovery history and audit

Retain qualified, unqualified, review-required, human-rejected and unapproved discovery candidates. Record run ID/inputs, operation/stage, source references, immutable package/manifest, agent metadata, raw and parsed responses, validation report, human decision/reviewer, CRM outcome/references, errors and retries. A failed or rejected run is not represented as a successfully created Assessment.

## 12. Generic target architecture

Keep responsibilities separate:

1. CLI / Command Layer.
2. Run Orchestrator.
3. CRM Repository / Adapter.
4. Package Assembler.
5. Research Agent Adapter.
6. Contract Validator.
7. Assessment Mapper.
8. Workflow / Approval Layer.
9. Run Store / Audit Layer.

## 13. Security and configuration

Never print or package secrets. Use environment variables or secure runtime secret storage with least privilege. Missing variable names may be reported without values. Protected secret files must have restrictive permissions and remain outside Git and research packages. Tests and logs must not expose secrets.

## 14. Runtime and testing environment

Identify the correct environment from repository documentation, Docker/devcontainer files, running containers, working directories, dependencies and test commands. Do not assume the host is correct. Run tests in the identified container when required. If the environment cannot be established, report the blocker rather than selecting an arbitrary container. Missing credentials stop operations that require them; do not fabricate credentials.

## 15. Repository strategy

Create a clean implementation from the intended base. Preserve uncommitted work, do not modify the legacy branch, and document the starting point. Existing code is read-only reference unless isolated reuse is justified. No runtime dependency on legacy repositories, subprocess execution paths or legacy configuration formats is introduced without explicit approval.

## 16. Testing strategy

Cover command and operation/stage validation, package and prompt/contract preservation, ID mapping, output validation, mandatory negatives, insufficient evidence, duplicate drafts, human-field protection, CRM/agent integration, persistence and approval, failure cases and secret redaction. Test in the identified runtime. Do not claim unexecuted tests passed.

## 17. Implementation milestones

1. Foundation: clean structure, architecture/configuration, explicit-operation CLI and verified test harness.
2. CRM reads: connectivity, templates, Assessments, references, sources and preflight checks.
3. Package and agent integration: immutable package, unchanged prompt/contract, adapter and tracking.
4. Validation and mapping: contract, IDs, evidence, qualification and CREATE/UPDATE mapping.
5. Review and persistence: approval, safe CREATE/UPDATE writes, transactions and audit.
6. End-to-end verification: integration, failure, security and container-based operational checks.

Do not implement all milestones in one uncontrolled change.

## 18. Definition of done

The eventual implementation has clean boundaries without legacy runtime dependence; requires explicit CREATE/UPDATE; selects the authoritative questions; passes prompt and contract unchanged; maps CREATE correlation IDs to new rows and UPDATE IDs to existing rows; blocks duplicate drafts; protects human fields; stages for human confirmation; writes safely; audits evidence/history; tests in the correct environment; and exposes no secrets.

**This document is the architectural baseline.** Deviations affecting CRM ownership, question identity, CREATE/UPDATE semantics, prompt handling, human-field protection or approval require explicit review before implementation.

## Unresolved implementation questions

- Actual CRM DocTypes, child-table links, field metadata, workflow states, permissions and duplicate-context definition require live metadata inspection.
- The correct test container cannot yet be verified because this repository defines no container and the Docker daemon is inaccessible in the current session.
- Research-agent provider, runtime secret mechanism, storage implementation and supported operation/stage combinations require configuration and integration design in later milestones.

note this document should be moved to docs folder
