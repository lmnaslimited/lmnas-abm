# Frappectl Container Verification

> **Historical status:** This was the initial CLI/environment check before persistent Docker Compose environment variables were configured. Its no-site-configured results are superseded by the later live CRM reads documented in [CRM read integration](crm-read-integration.md). Retained as a record of the initial verification only.

**Date:** 2026-11-25  
**Scope:** Read-only CLI verification inside Docker container `lmnas-frappectl`. No CRM documents or DocTypes were modified. No credentials, API secrets or keyring contents were displayed or inspected.

## Container and CLI

Container discovery command:

```sh
docker ps --filter name=lmnas-frappectl --format '{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}'
```

Result: container `lmnas-frappectl` (ID `f8b3c84383b6`, image `lmnas-frappectl:latest`) was running. A second Compose run container was also listed; verification used the explicitly requested named container.

Exact in-container commands and results:

| Command | Result |
|---|---|
| `docker exec lmnas-frappectl fr --version` | **Success:** `frappectl 0.26.0` |
| `docker exec lmnas-frappectl fr doctype --help` | **Success:** `doctype` supports `list` and `show`; `show` is described as showing fields, types and permissions. |
| `docker exec lmnas-frappectl fr doctype show --help` | **Success:** syntax is `fr doctype show [OPTIONS] {name}`; `--raw` prints full unprocessed metadata. |
| `docker exec lmnas-frappectl fr doc --help` | **Success:** `doc` supports `get`; help describes it as fetching one document by name. |
| `docker exec lmnas-frappectl fr doc get --help` | **Success:** syntax is `fr doc get [OPTIONS] {doctype} {name}`. |
| `docker exec lmnas-frappectl sh -lc 'command -v fr; head -n 1 "$(command -v fr)"; uv tool list'` | **Success:** executable is `/usr/local/bin/fr`, uses `/opt/uv-tools/frappectl/bin/python`; uv reports `frappectl v0.26.0` with `fr` and `frappectl` entry points. |
| `docker exec lmnas-frappectl fr auth --help` | **Success:** auth commands include `login`, `list`, `logout`, `default`, `configure`, and `whoami`. No login or profile changes were made. |
| `docker exec lmnas-frappectl fr config --help` | **Failure (expected command unavailable):** `No such command 'config'`. |

## CRM access and metadata attempts

A presence-only check inside the container reported `FRAPPE_SITE`, `FRAPPE_API_KEY`, and `FRAPPE_API_SECRET` as **missing**. Only variable names and set/missing status were emitted; values were never read or displayed.

The following read-only command was executed:

```sh
docker exec lmnas-frappectl fr doctype show 'CRM Organization'
```

**Failure, exit 2:** `No site configured. Run 'frappectl auth login <url>' or set FRAPPE_SITE, FRAPPE_API_KEY and FRAPPE_API_SECRET.` The command did not return DocType metadata.

Each of these raw metadata requests was also attempted individually, each with exit 2 and the same no-site-configured error:

```sh
docker exec lmnas-frappectl fr doctype show --raw 'CRM Assessment'
docker exec lmnas-frappectl fr doctype show --raw 'Assessment Template'
docker exec lmnas-frappectl fr doctype show --raw 'Assessment Questions'
docker exec lmnas-frappectl fr doctype show --raw 'Assessment Category'
docker exec lmnas-frappectl fr doctype show --raw 'Assessment Lookup Source'
```

**Metadata result:** No actual field names, types, options, child-table relationships, permissions or other DocType metadata could be retrieved. The CLI stopped during site resolution, before a CRM metadata response. These details remain unverified; no fields or relationships are inferred here.

## `fr doc get` investigation

The CLI help was successful and documents this syntax:

```sh
fr doc get {doctype} {name}
```

A safe syntax/initialization probe was executed without targeting an existing record:

```sh
docker exec lmnas-frappectl fr doc get 'CRM Organization' __read_only_syntax_probe__
```

It failed with exit 2 and the same `No site configured` error as the DocType requests. Therefore this run does **not** demonstrate a `doc get`-specific failure: `fr` has no resolved site/auth context, and the request never reached CRM. Whether `doc get` succeeds with a valid configured site remains untested. No credential profile or keyring contents were inspected, and no authentication was attempted.

A Python import probe for `frappectl` failed with `ModuleNotFoundError`; this is not evidence that the CLI is missing. The `fr` executable and uv tool installation were confirmed separately, and the CLI works for local help/version commands.

## Follow-up needed

A user with access to the container's approved secret mechanism must configure the site credentials in the container without sharing secret values in this report or conversation. Then rerun the read-only DocType commands above, using `--raw` to capture complete metadata, and retry `fr doc get` against an approved existing record. Until then, actual CRM schema details and `doc get` network behavior cannot be verified.
