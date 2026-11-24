from __future__ import annotations

import json
import shutil
import subprocess
from urllib.parse import quote


def api(endpoint: str, method: str = "GET", body: dict | None = None):
    """Call the configured frappectl REST API without exposing credentials."""
    if not shutil.which("fr"):
        raise RuntimeError("frappectl command `fr` is not installed or not on PATH")
    cmd = ["fr", "api", endpoint, "-X", method, "--json"]
    payload = None
    if body is not None:
        cmd += ["--input", "-"]
        payload = json.dumps(body, ensure_ascii=False)
    result = subprocess.run(cmd, input=payload, text=True, capture_output=True)
    if result.returncode:
        # CLI errors can include request data; do not surface raw output in audit records.
        raise RuntimeError(f"CRM API request failed (exit {result.returncode}); inspect frappectl locally")
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("CRM API returned non-JSON output") from exc
    return response.get("data", response) if isinstance(response, dict) else response


def get_doc(doctype: str, name: str):
    return api(f"document/{quote(doctype, safe='')}/{quote(name, safe='')}")


def list_docs(doctype: str, fields: list[str], filters: list | None = None):
    from urllib.parse import urlencode
    start, all_rows, seen = 0, [], set()
    while True:
        params = {"fields": json.dumps(fields, separators=(",", ":")), "start": start, "limit": 100, "order_by": "name asc"}
        if filters:
            params["filters"] = json.dumps(filters, separators=(",", ":"))
        rows = api(f"document/{quote(doctype, safe='')}?{urlencode(params)}") or []
        if not isinstance(rows, list):
            raise RuntimeError(f"CRM returned unexpected list response for {doctype}")
        if not rows:
            return all_rows
        for row in rows:
            if not row.get("name") or row["name"] in seen:
                raise RuntimeError(f"Unstable/incomplete pagination for {doctype}")
            seen.add(row["name"])
        all_rows.extend(rows)
        start += len(rows)


def doctype_meta(doctype: str) -> dict:
    """Fetch live DocType metadata; never infer field names from assumptions."""
    meta = api(f"doctype/{quote(doctype, safe='')}")
    if not isinstance(meta, dict):
        raise RuntimeError(f"Live metadata unavailable for {doctype}")
    fields = meta.get("fields") or meta.get("fields_json")
    if isinstance(fields, str):
        fields = json.loads(fields)
    if not isinstance(fields, list):
        raise RuntimeError(f"Live metadata for {doctype} has no readable field list")
    return {"name": meta.get("name") or doctype, "fields": fields, "raw": meta}
