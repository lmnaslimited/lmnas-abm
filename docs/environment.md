# Environment audit

- Mac checkout path: `/Users/arunkumar.ganesan/lmnas-frappectl`.
- Host shared-workspace path: `/Users/arunkumar.ganesan/lmnas-frappectl/workspace` (Compose bind source is relative `./workspace`).
- Container mount: `/workspace`; Compose service/container: `frappectl` / `lmnas-frappectl`.
- Dockerfile uses Python 3.12 slim, installs `uv`, and installs `frappectl` with `uv tool install --with keyrings.cryptfile frappectl`. It sets `PYTHON_KEYRING_BACKEND=keyrings.cryptfile.cryptfile.CryptFileKeyring`.
- Compose persists `/home/frappe/.config` and `/home/frappe/.cache` in named volumes; source workspace persists on host. Container restart is disabled (`restart: "no"`).
- This session could not connect to the Docker daemon due to socket permission denial. `fr` is not installed on the Mac PATH. Version, install details as running, URL/config and authentication health are unknown; no upgrade or authentication attempt was made.
- Next safe container checks: `docker compose exec -T frappectl fr --version`; inspect `fr --help` and documented config display with secrets redacted; use one harmless read-only CRM metadata request after confirming selected target. Avoid printing credentials or changing config.
