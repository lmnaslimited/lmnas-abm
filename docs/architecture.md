# Proposed architecture (Phase 2 design, not implemented)

Use `abm` as a thin command router over adapter modules. Existing projects remain intact and own their proven behavior during initial migration.

```text
abm CLI
 ├─ discovery adapter ── lmnas_discovery_pipeline CLI + existing SQLite/history
 ├─ research/assessment adapter ── lmnas-crm-research-orchestrator packages
 ├─ assessment research adapter ── lmnas_crm_research_engine
 ├─ contacts service ── validated research + live CRM Contact/Lead schemas
 ├─ shared CRM adapter ── `fr api` in configured Docker runtime
 └─ workflow/report adapter ── stage references to source run artifacts
```

The shared CRM adapter should be adopted only after parity checks inside Docker. It should expose schema metadata, search/list, get, create, update and read-back operations; redact credentials and response details in errors. Domain data should use typed records for organization identity, financial provenance, sources, assessments, contacts and sync outcomes. One `Decimal` normalization service should be the only path from reported money to `revenue_usd_m`.

Runtime data stays under the persistent application workspace or, where authoritative today, remains in the existing discovery/orchestrator workspaces and is referenced. No data move or source-project mutation occurs without a migration plan.
