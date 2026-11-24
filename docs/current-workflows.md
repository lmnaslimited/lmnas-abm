# Current workflows

## Discovery

`lmnas_discovery_pipeline` builds a run from configured regions and CRM/reference snapshots, generates a research input ZIP and prompt, accepts returned research packages, validates evidence and assessment answers, applies disposition decisions, writes reports, and uses SQLite for discovery history. Its importer has duplicate checks, dry-run/confirmation gates, CRM writes, read-back checks and local audit markers. Current run `20261124T113025Z` contains two candidate packages, both marked `HUMAN_REVIEW`; collection report reports no validation errors.

## Research and assessments

The research orchestrator creates per-organization outgoing packages with organization profile, product context, methodology, schemas, and tasks for organization, CPQ, Tender Intelligence and LENSIPS. Human/agent research results return as ZIPs, are validated/collected, and assessment AI fields can be written back through `fr`. Product and organization templates are drawn from CRM records; local `inspection/` contains snapshots.

## Existing state and recovery

Discovery history is `workspace/lmnas_discovery_pipeline/workspace/history/discovery.sqlite3`. Runs carry manifests and copies of input snapshots. Imports keep `in_progress` and `audit` JSON records. Orchestrator runs preserve manifests, validations and writeback summaries. These are complementary existing state stores; Phase 2 should retain them and coordinate by references rather than create a duplicate account database without a migration need.

## Intended future Contact/Lead stage

After a person is approved, research validation precedes Contact resolution/create, then Lead resolution/create. Both DocTypes must be read live for fields and relationship semantics. Store a stable identity and sync outcome in a local audit record. If Lead creation fails after Contact creation, a retry must resolve the Contact first. Do not invent relationship fields, statuses, or product fields; use confirmed CRM metadata and preserve existing human-owned values.
