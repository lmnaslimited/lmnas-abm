from __future__ import annotations

import json
import shutil
import subprocess
from urllib.parse import quote, urlencode


def api(endpoint: str, method: str = "GET", body: dict | None = None):
    if not shutil.which("fr"):
        raise RuntimeError("frappectl command `fr` is not installed or not on PATH")
    cmd = ["fr", "api", endpoint, "-X", method, "--json"]
    payload = json.dumps(body, ensure_ascii=False) if body is not None else None
    if body is not None:
        cmd += ["--input", "-"]
    result = subprocess.run(cmd, input=payload, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"CRM API request failed (exit {result.returncode}); inspect frappectl locally")
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("CRM API returned non-JSON output") from exc
    return response.get("data", response) if isinstance(response, dict) and "data" in response else response


def get_doc(doctype: str, name: str):
    return api(f"document/{quote(doctype, safe='')}/{quote(name, safe='')}")


def list_docs(doctype: str, fields: list[str], filters: list | None = None):
    start, rows, seen = 0, [], set()
    while True:
        params = {"fields": json.dumps(fields, separators=(",", ":")), "start": start,
                  "limit": 100, "order_by": "name asc"}
        if filters:
            params["filters"] = json.dumps(filters, separators=(",", ":"))
        page = api(f"document/{quote(doctype, safe='')}?{urlencode(params)}") or []
        if not isinstance(page, list):
            raise RuntimeError(f"CRM returned unexpected list response for {doctype}")
        if not page:
            return rows
        for row in page:
            if not row.get("name") or row["name"] in seen:
                raise RuntimeError(f"Unstable/incomplete pagination for {doctype}")
            seen.add(row["name"])
        rows.extend(page)
        start += len(page)


def doctype_meta(doctype: str):
    """Fetch DocType metadata through the existing frappectl interface."""
    # Metadata endpoint behavior varies by installed frappectl/Frappe version.
    # This uses the CLI's documented `doctype show` API when available.
    if not shutil.which("fr"):
        raise RuntimeError("frappectl command `fr` is not installed or not on PATH")
    result = subprocess.run(["fr", "doctype", "show", doctype, "--json"], text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"CRM metadata request failed (exit {result.returncode}); inspect frappectl locally")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("CRM metadata returned non-JSON output") from exc
    return data.get("data", data) if isinstance(data, dict) else data
