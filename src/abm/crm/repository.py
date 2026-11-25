"""CRM read repository built over the provider-neutral ``fr api`` client."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from abm.crm.client import FrappeAPIClient


# Verified from live CRM Organization metadata: these are its principal
# organization-mapping Link targets (other optional links can be fetched using
# list_reference_documents when a caller needs them).
ORGANIZATION_REFERENCE_DOCTYPES = {
    "currency": "Currency",
    "territory": "CRM Territory",
    "industry": "CRM Industry",
}


class CRMRepository:
    """Read-only CRM retrieval methods for CREATE and UPDATE preparation."""

    def __init__(self, api: FrappeAPIClient | None = None) -> None:
        self.api = api or FrappeAPIClient()

    def get_document(self, doctype: str, name: str) -> dict[str, Any]:
        return self.api.get_document(doctype, name)

    def list_documents(
        self,
        doctype: str,
        *,
        fields: Sequence[str] = ("name",),
        filters: Sequence[Sequence[Any]] | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        return self.api.list_documents(
            doctype, fields=fields, filters=filters, page_size=page_size
        )

    def get_organization(self, organization_name: str) -> dict[str, Any]:
        """Fetch a CRM Organization, including its embedded child tables."""
        return self.get_document("CRM Organization", organization_name)

    def get_assessment_template_for_create(self, template_name: str) -> dict[str, Any]:
        """Fetch the CREATE question source and its embedded child rows."""
        return self.get_document("Assessment Template", template_name)

    def get_assessment_for_update(self, assessment_name: str) -> dict[str, Any]:
        """Fetch an existing Assessment and its authoritative question rows."""
        return self.get_document("CRM Assessment", assessment_name)

    def get_assessment_categories(
        self, question_rows: Sequence[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Fetch each distinct Assessment Category linked by question rows."""
        category_names = dict.fromkeys(
            row["assessment_category"]
            for row in question_rows
            if row.get("assessment_category")
        )
        return {
            name: self.get_document("Assessment Category", name)
            for name in category_names
        }

    def get_organization_reference_data(
        self,
        additional_link_doctypes: Mapping[str, str] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Retrieve values for verified Organization links and optional links.

        Currency, territory, and industry are fetched by default. Pass other
        metadata-confirmed field-to-DocType pairs (for example Address or User)
        when a specific mapping operation needs those broader reference sets.
        """
        references = dict(ORGANIZATION_REFERENCE_DOCTYPES)
        references.update(additional_link_doctypes or {})
        return {
            fieldname: self.list_documents(doctype, fields=("name",))
            for fieldname, doctype in references.items()
        }

    def list_reference_documents(
        self, doctype: str, *, fields: Sequence[str] = ("name",)
    ) -> list[dict[str, Any]]:
        """Fetch other Link targets (for example Address or User) on demand."""
        return self.list_documents(doctype, fields=fields)

    def get_lookup_sources_for_template(
        self, template: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Resolve lookup records referenced by template/question multi-selects.

        Direct list access to the plural child DocType is currently denied for
        this configured user. The six live Templates presently contain no source
        references. An empty template returns without a request; referenced
        singular source documents are fetched individually and errors propagate.
        """
        names: dict[str, None] = {}
        rows = list(template.get("lookup_sources") or [])
        for question in template.get("assessment_questions") or []:
            rows.extend(question.get("additional_lookup_sources") or [])
        for row in rows:
            name = row.get("lookup_source") or row.get("source") or row.get("name")
            if name:
                names[name] = None
        return [self.get_document("Assessment Lookup Source", name) for name in names]
