# LMNAs ABM

Clean foundation for CRM-driven Account-Based Marketing research orchestration. The approved architecture is in [architecture](docs/architecture.md). The current implementation includes explicit CREATE/UPDATE command validation, read-only CRM catalogue retrieval, territory/category source planning and immutable package preparation. It does not invoke a research agent or perform CRM writes or approvals.

See [CRM read integration](docs/crm-read-integration.md) for the `fr api` interface, schema verification status, retrieval methods and permission limits. See [package schema](docs/package-schema.md) for package files.

## Project structure

- `src/abm/cli.py` — command parsing and explicit assessment operation.
- `src/abm/orchestration/` — Prepare → Collect → Confirm coordination boundary.
- `src/abm/crm/client.py` — read-only `fr api` transport.
- `src/abm/crm/repository.py` — CREATE/UPDATE read contexts, embedded child-row preservation, full source catalogue and category/reference reads.
- `src/abm/package/source_resolver.py` — territory-aware phases and category/explicit associations.
- `src/abm/package/assembler.py` — deterministic package files and checksums.
- `src/abm/package/preparation.py` — CRM context/catalogue/tree composition into a prepared package.
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

The CLI still validates commands only; package preparation is currently a Python API and does not start research or persistence.
