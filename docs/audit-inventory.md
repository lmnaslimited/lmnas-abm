# Workspace audit inventory (Phase 1)

Audit scope: mounted workspace at `/Users/arunkumar.ganesan/lmnas-frappectl/workspace`, seen from the Mac host. Docker Compose maps host `./workspace` to container `/workspace`. Original project files were inspected read-only; the only newly created/modified paths are under `workspace/lmnas-abm` from the interrupted attempt and this audit.

| Component | Purpose / entry point | Inputs and outputs | CRM / state | Dependencies, tests, disposition |
|---|---|---|---|---|
| `lmnas_discovery_pipeline` | Account discovery, screening, evidence quality and import. CLI: `python -m src.pipeline` (see README/help). | JSON research packages, run ZIPs/manifests; screened candidates, CRM snapshots and reports. | Shared `fr` CLI, `CRM Organization`, assessment templates, Addresses; persistent SQLite `workspace/history/discovery.sqlite3`, runs, snapshots, import audit. | Python stdlib and `requirements.txt`; unit/import/quality tests. Reuse as a wrapped component; keep its history authoritative. |
| `lmnas-crm-research-orchestrator` | Research package assembly, validation, assessment writeback. Entry `src/orchestrator.py`. | Organization ID and research result ZIPs; outgoing packages, validation, collected results and writeback summary. | Calls `fr api`; reads/writes assessment AI fields; package/run artifacts in project workspace. | Python CLI; tests `tests/test_research_output.py`. Reuse/wrap directly. |
| `lmnas_crm_research_engine` | Assessment question research queue generation and prompt. Entry `research_engine.py`. | CRM assessment JSON exports; queue CSV/JSON and preview template. | Reads exported CRM assessment data; no direct API evidenced. | Python stdlib; no tests found. Reuse prompt/data conventions, evaluate wrapper. |
| `lmnas-organization-importer` | Earlier JSON-to-CRM Organization import. Entry `importer.py`. | Files under `data/incoming`; moves to created/skipped/failed and logs. | Direct REST API client with token configuration; CRM Organization creates and duplicate check. | Python requests likely; no tests found. Treat as reference only; do not use alongside pipeline importer without consolidation. |
| `assessment-automation` | Sanitized or exported assessment input snapshots. | `input/CRM-ASS-*.json`, ZIP. | No live API behavior observed. | Useful fixtures/reference; inspect provenance before tests. |
| `inspection` | CRM Organization and three Product Assessment snapshots/templates. | Local JSON snapshots. | Captures actual schema examples, not live metadata proof. | Reuse for mapping; verify live fields inside Docker before writes. |
| `workspace/lmnas-abm` | Interrupted attempt plus this Phase 1 audit. | Initially partial `pyproject.toml`, package stubs and `crm/client.py`; now audit docs. | No existing CRM state. | Not a complete or approved architecture. Preserve useful files, review before Phase 2. |
| ZIPs directly under workspace | Archived project snapshots. | `lmnas-organization-importer.zip`, `lmnas-crm-research-orchestrator-v3.zip`, engine ZIP, assessment ZIP. | None directly. | Compare only when a discrepancy warrants it; do not extract over current projects. |

## Runtime assets

Discovery has durable SQLite history, run manifests/input packages, CRM snapshot, received research ZIPs and import audit/in-progress markers. The orchestrator has incoming/outgoing package artifacts and per-run writeback summaries. The importer has logs and created/skipped sample payloads. These are existing user data; preserve them and keep runtime data out of source control.

## Audit limits

Docker daemon access from this session was denied (`permission denied` on the Docker socket). `fr` is absent from the Mac PATH. Therefore live CRM metadata, frappectl version/config/authentication, and server-side assessment traceback could not be checked. No CRM calls or writes were made. `workspace` itself is not a Git repository in this checkout; check the intended repository boundary before initializing Git.
