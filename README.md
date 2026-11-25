# LMNAs ABM unified workflow

The `abm` CLI provides a shared entry point over the existing discovery pipeline and CRM research orchestrator. Existing source projects remain unchanged and own the established discovery history, prompts, package contracts, validation and CRM writeback behavior.

## Install and run

From this directory:

```bash
python3 -m pip install -e .
abm --help
```

CRM-dependent commands must run in the configured `frappectl` Docker container with its existing authentication volume mounted. Until Docker/CRM access is available, use help and offline domain checks only.

```bash
abm discover --regions Europe "Middle East" --target 2
abm research --org-id "EXACT CRM ORGANIZATION NAME" --dry-run
abm assess organization --org-id "EXACT CRM ORGANIZATION NAME" --dry-run
abm assess products --org-id "EXACT CRM ORGANIZATION NAME" --all --dry-run
abm status --org-id "EXACT CRM ORGANIZATION NAME"
abm report --org-id "EXACT CRM ORGANIZATION NAME"
```

Assessment research retains the source orchestrator's prepare/collect/apply package contract. Use `abm assess organization --help` for collection and apply flags. A `--confirm` flag is required by the underlying orchestrator for CRM assessment writeback. Product assessment operations fail closed because the existing resolver covers only organization-linked assessments and CRM product reference/creation rules could not be verified live.

`abm run` currently prepares the established research package and does not claim an unattended end-to-end run: the research result ZIP and review/authorization boundary remain explicit workflow stages.

## Shared engine and architecture

```text
abm CLI
  ├─ discovery adapter ── existing discovery pipeline + history DB
  ├─ research/assessment engine ── existing orchestrator functions and prompts
  ├─ domain ── shared typed records + Decimal financial normalization
  ├─ CRM adapter ── frappectl CLI (one client for ABM commands)
  └─ workflow/report ── artifact status and thin orchestration
```

See the [reuse map](docs/reuse-and-migration-map.md), [workflow](docs/workflow.md), and [known issues](docs/known-issues.md). Contact identification is research-only; Contact/Lead CRM writes are not implemented.

## Regression checks

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

No production CRM writes were made while implementing this application.
