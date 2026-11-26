"""Read-only transport for the configured Frappe CLI's ``fr api`` command."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from urllib.parse import quote, unquote


class FrappeAPIError(RuntimeError):
    """A sanitized API transport, response, or permission error."""


Runner = Callable[..., subprocess.CompletedProcess[str]]


class FrappeAPIClient:
    """Call Frappe API v2 through ``fr api`` without handling credentials.

    The CLI obtains site credentials from its existing container configuration.
    This client deliberately never includes subprocess stderr/stdout in errors,
    because CLI/server diagnostics must not leak authentication material.
    """

    def __init__(
        self,
        executable: str = "fr",
        *,
        runner: Runner | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.executable = executable
        self._runner = runner or subprocess.run
        self.timeout = timeout
        self.request_metrics: dict[str, dict[str, float | int]] = {}

    def _record_request(self, path: str, elapsed: float, failed: bool) -> None:
        parts = path.split("/")
        doctype = unquote(parts[1]) if len(parts) > 1 else "unknown"
        row = self.request_metrics.setdefault(
            doctype, {"requests": 0, "failures": 0, "elapsed_seconds": 0.0}
        )
        row["requests"] += 1
        row["failures"] += int(failed)
        row["elapsed_seconds"] += elapsed

    def get(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        """Perform one GET through ``fr api`` and parse its JSON response."""
        if not path or path.startswith("/"):
            raise ValueError("API path must be a non-empty relative path")
        command = [self.executable, "api"]
        for key, value in (params or {}).items():
            if isinstance(value, (list, dict, bool)) or value is None:
                encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                command.extend(("-F", f"{key}:={encoded}"))
            else:
                command.extend(("-F", f"{key}={value}"))
        command.append(path)

        if shutil.which(self.executable) is None and self._runner is subprocess.run:
            raise FrappeAPIError("Frappe CLI `fr` is not installed or not on PATH")
        started = time.perf_counter()
        try:
            result = self._runner(
                command,
                text=True,
                capture_output=True,
                check=False,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            self._record_request(path, time.perf_counter() - started, True)
            raise FrappeAPIError("Frappe API request timed out") from exc
        except OSError as exc:
            self._record_request(path, time.perf_counter() - started, True)
            raise FrappeAPIError("Could not execute Frappe CLI `fr api`") from exc

        if result.returncode != 0:
            self._record_request(path, time.perf_counter() - started, True)
            raise FrappeAPIError(f"Frappe API request failed (fr api exit {result.returncode})")
        try:
            response = json.loads(result.stdout)
        except (TypeError, json.JSONDecodeError) as exc:
            self._record_request(path, time.perf_counter() - started, True)
            raise FrappeAPIError("Frappe API returned invalid JSON") from exc
        self._record_request(path, time.perf_counter() - started, False)
        return response

    def metrics_snapshot(self) -> dict[str, dict[str, float | int]]:
        return {doctype: dict(values) for doctype, values in sorted(self.request_metrics.items())}

    def get_document(self, doctype: str, name: str) -> dict[str, Any]:
        """Fetch one document using the read-only API v2 document endpoint."""
        if not doctype or not name:
            raise ValueError("doctype and document name are required")
        path = f"document/{quote(doctype, safe='')}/{quote(name, safe='')}"
        response = self.get(path)
        if not isinstance(response, dict):
            raise FrappeAPIError("Frappe document response was not a JSON object")
        return response

    def list_documents(
        self,
        doctype: str,
        *,
        fields: Sequence[str] = ("name",),
        filters: Sequence[Sequence[Any]] | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch all matching documents using the verified ``limit``/``start`` API.

        Frappe API v2 ignores the legacy ``limit_page_length`` and
        ``limit_start`` parameter names here. ``limit`` and ``start`` were
        verified against live Assessment Category pagination.
        """
        if not doctype:
            raise ValueError("doctype is required")
        if page_size < 1:
            raise ValueError("page_size must be positive")
        selected_fields = list(dict.fromkeys((*fields, "name")))
        output: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        start = 0
        while True:
            params: dict[str, Any] = {
                "fields": selected_fields,
                "limit": page_size,
                "start": start,
            }
            if filters is not None:
                params["filters"] = list(filters)
            path = f"document/{quote(doctype, safe='')}"
            rows = self.get(path, params)
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise FrappeAPIError("Frappe document-list response was not a JSON array of objects")
            if not rows:
                return output
            output.extend(rows)
            start += len(rows)
            if len(rows) > page_size:
                raise FrappeAPIError("Frappe document-list returned more rows than the requested page size")
            identities = [row.get("name") for row in rows]
            if any(not isinstance(name, str) or not name for name in identities):
                raise FrappeAPIError("Frappe document-list page contains a row without a name")
            if len(set(identities)) != len(identities):
                raise FrappeAPIError("Frappe document-list page contains duplicate identities")
            repeated = seen_names.intersection(identities)
            if repeated:
                raise FrappeAPIError("Frappe document-list pagination repeated document identities")
            seen_names.update(identities)
            if len(rows) < page_size:
                return output
