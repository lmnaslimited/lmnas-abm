# LMNAs ABM

Clean foundation for CRM-driven Account-Based Marketing research orchestration. The approved architecture is in [architecture.md](architecture.md). The current implementation includes explicit CREATE/UPDATE command validation and a read-only Frappe CRM client/repository; it does not perform CRM writes, invoke a research agent, assemble run packages or manage approvals.

See [CRM read integration](docs/crm-read-integration.md) for the verified `fr api` interface, live CRM schemas, retrieval methods and permission limits.

## Project structure

- `src/abm/cli.py` — command parsing and explicit assessment operation.
- `src/abm/orchestration/` — Prepare → Collect → Confirm coordination boundary.
- `src/abm/crm/client.py` — read-only `fr api` transport.
- `src/abm/crm/repository.py` — Organization, Template, Assessment and reference-data reads.
- `src/abm/package/` — immutable package assembly boundary.
- `src/abm/agent/` — provider-neutral research adapter boundary.
- `src/abm/validation/` — output contract validation boundary.
- `src/abm/assessment/` — question mapping boundary.
- `src/abm/workflow/` — human review boundary.
- `src/abm/audit/` — run history boundary.
- `tests/` — deterministic standard-library unit tests.

## Development and tests

The repository-level Compose service is `frappectl` / `lmnas-frappectl`, with `/workspace` as its working directory and this project mounted at `/workspace/lmnas-abm`. The Frappe CLI must be configured in that container. CRM reads use `fr api`; `fr doc get` is intentionally not used.

```sh
cd /workspace/lmnas-abm
PYTHONPATH=src python -m unittest discover -s tests -v
```

The unit tests use mocked API responses and need no production CRM credentials. Live CRM access should only be exercised inside the configured container.

## CLI

```sh
PYTHONPATH=src python -m abm.cli run --assessment-operation CREATE
PYTHONPATH=src python -m abm.cli run --assessment-operation UPDATE --research-stage FULL_ASSESSMENT
```

This validates the command only; it does not yet start a CRM or research workflow.
