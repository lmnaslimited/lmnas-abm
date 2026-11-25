# LMNAs ABM

Clean foundation for CRM-driven Account-Based Marketing research orchestration. The architecture baseline is [architecture.md](architecture.md). This milestone provides only command validation and separated module boundaries; it does not connect to CRM, invoke a research agent, assemble packages or persist results.

## Project structure

- `src/abm/cli.py` — command parsing and explicit assessment operation.
- `src/abm/orchestration/` — Prepare → Collect → Confirm coordination boundary.
- `src/abm/crm/` — CRM repository boundary.
- `src/abm/package/` — immutable package assembly boundary.
- `src/abm/agent/` — provider-neutral research adapter boundary.
- `src/abm/validation/` — output contract validation boundary.
- `src/abm/assessment/` — question mapping boundary.
- `src/abm/workflow/` — human review boundary.
- `src/abm/audit/` — run history boundary.
- `tests/` — deterministic standard-library unit tests.

The legacy implementation on `feature/unified-assessment-engine` is retained as read-only reference. This branch contains no runtime import or subprocess dependency on legacy projects.

## Development and tests

Repository-level Docker setup is in the parent workspace at `/Users/arunkumar.ganesan/lmnas-frappectl/Dockerfile` and `docker-compose.yml`. It defines service/container `frappectl` / `lmnas-frappectl`, Python 3.12 image and `/workspace` working directory, with this repository mounted at `/workspace/lmnas-abm`.

The intended test command inside that service is:

```sh
cd /workspace/lmnas-abm
python -m unittest discover -s tests -v
```

The container runtime and dependencies could not be verified in this pass: Docker daemon access returned permission denied for the configured socket. Start/access the parent Compose service, then run the command above. Do not substitute a different running container without confirming it belongs to this project.

Host Python 3.14 is present. `pytest` is not installed, and this foundation uses `unittest` without third-party runtime dependencies. Host test command (used only as a fallback because the required Docker service was inaccessible):

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## CLI

The operation is mandatory and independent of stage:

```sh
PYTHONPATH=src python3 -m abm.cli run --assessment-operation CREATE
PYTHONPATH=src python3 -m abm.cli run --assessment-operation UPDATE --research-stage FULL_ASSESSMENT
```

This validates and displays the requested command only. It performs no CRM or research operation.

## Configuration and secrets

No environment variables are required for this foundation. CRM and research integrations are not implemented. Add integration-specific configuration names and secure loading behavior only when those integrations are designed; never put secret values in Git, test output or run packages.

## Decisions and unresolved items

- Base: `main` at `2ff3bdb`; clean branch: `feature/clean-abm-foundation`.
- The parent workspace Docker service is the intended test environment, but daemon access and installed in-container dependencies remain unverified.
- Live CRM metadata, duplicate-context rules, workflow states, agent provider, runtime secret mechanism and run storage require later integration milestones.
