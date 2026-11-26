# LMNAs ABM

Clean foundation for CRM-driven Account-Based Marketing research orchestration. The approved architecture is in [architecture](docs/architecture.md). The current implementation includes explicit CREATE/UPDATE command validation, read-only CRM catalogue retrieval, territory/category source planning and immutable package preparation. It does not invoke a research agent or perform CRM writes or approvals.

See [CRM read integration](docs/crm-read-integration.md) for the `fr api` interface, schema verification status, retrieval methods and permission limits. See [package schema](docs/package-schema.md) for package files.

## Project structure

- `src/abm/cli.py` — truthful run validation and executable regional CREATE package preparation.
- `src/abm/config.py` and `config/abm.toml` — non-secret TOML defaults; template and region remain unset until selected.
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

## Configuration and CLI

Edit `config/abm.toml` or pass a separate file with `--config`. The values under `[defaults]` are intentionally empty for the CRM template and region: choose them explicitly rather than inheriting an assumed business scope. Precedence is CLI option, then TOML setting, then a clear missing-value error. Relative output paths use the current working directory. Configuration rejects credential-like fields and must not contain secrets.

Prepare an immutable regional package (CREATE only):

```sh
PYTHONPATH=src python -m abm.cli prepare \
  --assessment-operation CREATE \
  --research-stage DISCOVERY \
  --template "ASSTP-CRM Organization-01" \
  --region Europe
```

The command reads the selected template, complete source catalogue and CRM Territory tree, bulk retrieves all CRM Organizations for duplicate exclusions, resolves applicable sources, and writes a unique projected package with a verified ZIP inside that package directory. `--template`, `--region`, and `--output-dir` override TOML defaults; `--config` selects another configuration file. The manifest records CRM API request counts and timings by DocType.

The `run` command still only validates an operation/stage request and does not execute research. UPDATE package preparation, country CLI execution, agent invocation, output validation, approval and CRM persistence are unsupported.
