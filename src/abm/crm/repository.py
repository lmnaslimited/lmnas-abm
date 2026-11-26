"""Read-only CRM repository built over the Frappe ``fr api`` client."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from abm.crm.client import FrappeAPIClient, FrappeAPIError


# Verified from live CRM Organization metadata. Other Link targets are fetched
# only when a caller explicitly requests them.
ORGANIZATION_REFERENCE_DOCTYPES = {
    "currency": "Currency",
    "territory": "CRM Territory",
    "industry": "CRM Industry",
}


class CRMReadContextError(RuntimeError):
    """A referenced CRM document cannot form a complete read context."""


def _is_enabled(disabled: Any) -> bool:
    return str(disabled).strip().lower() not in {"1", "true", "yes"}


SOURCE_CHILD_TABLES = {
    "applicable_territories": ("Territories", "territory", "CRM Territory"),
    "applicable_assessment_categories": (
        "Assessment Categories", "assessment_category", "Assessment Category"
    ),
}


def _validate_source_document(source: dict[str, Any]) -> None:
    if not isinstance(source.get("source_name"), str) or not source["source_name"].strip():
        raise CRMReadContextError(f"Source {source.get('name')!r} has no source_name")
    url = source.get("url")
    parsed = urlparse(url) if isinstance(url, str) else None
    if not isinstance(url, str) or not url.strip() or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CRMReadContextError(f"Source {source.get('name')!r} has no usable URL")
    for field, (child_doctype, link_field, _target) in SOURCE_CHILD_TABLES.items():
        rows = source.get(field)
        if not isinstance(rows, list):
            raise CRMReadContextError(f"Source {source.get('name')!r} has an invalid {field!r} child table")
        for row in rows:
            if (not isinstance(row, dict) or not isinstance(row.get("name"), str)
                    or not isinstance(row.get(link_field), str) or not row[link_field]
                    or row.get("doctype") != child_doctype
                    or row.get("parent") != source.get("name")
                    or row.get("parentfield") != field
                    or row.get("parenttype") != "Assessment Lookup Source"):
                raise CRMReadContextError(f"Source {source.get('name')!r} has malformed rows in {field!r}")


def _validate_source_references(repository: "CRMRepository", source: dict[str, Any]) -> None:
    for field, (_child_doctype, link_field, doctype) in SOURCE_CHILD_TABLES.items():
        seen: set[str] = set()
        for row in source[field]:
            identity = row[link_field]
            if identity in seen:
                raise CRMReadContextError(f"Source {source['name']!r} duplicates reference {identity!r}")
            seen.add(identity)
            repository._source_reference_names.setdefault(doctype, set()).add(identity)


@dataclass(frozen=True)
class CreateReadContext:
    """Authoritative CREATE inputs and separately resolved linked records."""

    assessment_operation: str
    assessment_template: dict[str, Any]
    assessment_questions: list[dict[str, Any]]
    question_category_links: list[dict[str, Any]]
    assessment_categories: dict[str, dict[str, Any]]
    lookup_source_links: list[dict[str, Any]]
    lookup_source_records: dict[str, dict[str, Any]]
    organization: dict[str, Any] | None
    organization_reference_data: dict[str, list[dict[str, Any]]]


@dataclass(frozen=True)
class UpdateReadContext:
    """Existing Assessment inputs; embedded Assessment rows remain authoritative."""

    assessment_operation: str
    assessment: dict[str, Any]
    assessment_questions: list[dict[str, Any]]
    assessment_template_name: str | None
    template_lookup_source_rows: list[dict[str, Any]]
    question_category_links: list[dict[str, Any]]
    assessment_categories: dict[str, dict[str, Any]]
    lookup_source_links: list[dict[str, Any]]
    lookup_source_records: dict[str, dict[str, Any]]
    organization: dict[str, Any] | None
    organization_reference_data: dict[str, list[dict[str, Any]]]


class CRMRepository:
    """Read-only CRM retrieval methods for CREATE and UPDATE preparation."""

    def __init__(self, api: FrappeAPIClient | None = None) -> None:
        self.api = api or FrappeAPIClient()
        self._source_reference_names: dict[str, set[str]] = {}

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

    def get_source_catalogue(self, *, page_size: int = 100) -> dict[str, dict[str, Any]]:
        """Read and validate every enabled lookup source master.

        Child-table values are preserved exactly as returned by the full
        document endpoint. Their Link targets are checked against live CRM
        identities before the catalogue is returned.
        """
        try:
            rows = self.list_documents(
                "Assessment Lookup Source", fields=("name", "disabled"), page_size=page_size
            )
        except FrappeAPIError as exc:
            raise CRMReadContextError(
                "Could not list Assessment Lookup Source records with the configured CRM principal"
            ) from exc
        names: set[str] = set()
        source_names: set[str] = set()
        catalogue: dict[str, dict[str, Any]] = {}
        self._source_reference_names = {}
        for row in rows:
            name = row.get("name")
            if not isinstance(name, str) or not name.strip():
                raise CRMReadContextError("Source catalogue list contains a row without a name")
            if name in names:
                raise CRMReadContextError(f"Source catalogue contains duplicate identity {name!r}")
            names.add(name)
            if not _is_enabled(row.get("disabled")):
                continue
            try:
                doc = self.get_document("Assessment Lookup Source", name)
            except FrappeAPIError as exc:
                raise CRMReadContextError(f"Enabled source {name!r} could not be read") from exc
            if doc.get("name") != name:
                raise CRMReadContextError(f"Enabled source {name!r} returned a mismatched identity")
            if not _is_enabled(doc.get("disabled")):
                continue
            _validate_source_document(doc)
            _validate_source_references(self, doc)
            source_name = doc["source_name"].strip()
            if source_name in source_names:
                raise CRMReadContextError(f"Source catalogue contains duplicate source_name {source_name!r}")
            source_names.add(source_name)
            catalogue[name] = doc
        for doctype, referenced in self._source_reference_names.items():
            try:
                available = {row["name"] for row in self.list_documents(doctype, fields=("name",))}
            except FrappeAPIError as exc:
                raise CRMReadContextError(f"Cannot validate references to {doctype}") from exc
            missing = sorted(referenced - available)
            if missing:
                raise CRMReadContextError(f"Source catalogue references missing {doctype} record(s): {missing!r}")
        return catalogue

    @staticmethod
    def get_question_category_links(
        question_rows: Sequence[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Keep category joins keyed to each original question row and order."""
        return [
            {
                "question_row_name": row.get("name"),
                "question_idx": row.get("idx"),
                "assessment_category": row.get("assessment_category"),
            }
            for row in question_rows
        ]

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

    @staticmethod
    def _lookup_row_name(row: Mapping[str, Any], location: str) -> str:
        name = row.get("lookup_source")
        if not isinstance(name, str) or not name.strip():
            row_id = row.get("name", "<unknown child row>")
            raise CRMReadContextError(
                f"Lookup-source child row {row_id!r} at {location} has no lookup_source link"
            )
        return name

    def _resolve_lookup_sources(
        self,
        *,
        template_rows: Sequence[dict[str, Any]] = (),
        question_rows: Sequence[dict[str, Any]] = (),
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        """Preserve parent rows and resolve only their distinct master links."""
        links: list[dict[str, Any]] = []
        unique_names: dict[str, None] = {}

        for row in template_rows:
            name = self._lookup_row_name(row, "template.lookup_sources")
            links.append({
                "location": "template.lookup_sources",
                "question_row_name": None,
                "question_idx": None,
                "child_row_name": row.get("name"),
                "child_row_idx": row.get("idx"),
                "lookup_source": name,
                "child_row": row,
            })
            unique_names[name] = None

        for question in question_rows:
            rows = question.get("additional_lookup_sources") or []
            for row in rows:
                name = self._lookup_row_name(
                    row,
                    f"assessment_questions[{question.get('name', '<unknown>')}].additional_lookup_sources",
                )
                links.append({
                    "location": "assessment_questions[].additional_lookup_sources",
                    "question_row_name": question.get("name"),
                    "question_idx": question.get("idx"),
                    "child_row_name": row.get("name"),
                    "child_row_idx": row.get("idx"),
                    "lookup_source": name,
                    "child_row": row,
                })
                unique_names[name] = None

        records: dict[str, dict[str, Any]] = {}
        for name in unique_names:
            try:
                record = self.get_document("Assessment Lookup Source", name)
            except FrappeAPIError as exc:
                raise CRMReadContextError(
                    f"Referenced Assessment Lookup Source {name!r} could not be retrieved"
                ) from exc
            if record.get("name") != name:
                raise CRMReadContextError(
                    f"Referenced Assessment Lookup Source {name!r} returned a mismatched identity"
                )
            source_name = record.get("source_name")
            if not isinstance(source_name, str) or not source_name.strip():
                raise CRMReadContextError(
                    f"Referenced Assessment Lookup Source {name!r} has no source_name metadata"
                )
            url = record.get("url")
            if not isinstance(url, str) or not url.strip():
                raise CRMReadContextError(
                    f"Referenced Assessment Lookup Source {name!r} has no usable URL"
                )
            if not _is_enabled(record.get("disabled")):
                raise CRMReadContextError(f"Explicitly linked source {name!r} is disabled")
            _validate_source_document(record)
            records[name] = record
        return links, records

    def get_lookup_sources_for_template(
        self, template: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Return only referenced master records; never list the child DocType."""
        links, records = self._resolve_lookup_sources(
            template_rows=template.get("lookup_sources") or [],
            question_rows=template.get("assessment_questions") or [],
        )
        # Child rows remain embedded in `template`; returning records separately
        # prevents enrichment from replacing their identity or sequence.
        del links
        return records

    def prepare_create_read_context(
        self,
        template_name: str,
        *,
        organization_name: str | None = None,
        include_organization_reference_data: bool | None = None,
    ) -> CreateReadContext:
        """Prepare CREATE reads from the selected Template's question set."""
        template = self.get_assessment_template_for_create(template_name)
        questions = template.get("assessment_questions") or []
        template_source_rows = template.get("lookup_sources") or []
        lookup_links, source_records = self._resolve_lookup_sources(
            template_rows=template_source_rows,
            question_rows=questions,
        )
        categories = self.get_assessment_categories(questions)

        organization = (
            self.get_organization(organization_name) if organization_name else None
        )
        should_read_references = include_organization_reference_data
        if should_read_references is None:
            should_read_references = template.get("document_type") == "CRM Organization"
        references = (
            self.get_organization_reference_data()
            if should_read_references
            else {}
        )
        return CreateReadContext(
            assessment_operation="CREATE",
            assessment_template=template,
            assessment_questions=questions,
            question_category_links=self.get_question_category_links(questions),
            assessment_categories=categories,
            lookup_source_links=lookup_links,
            lookup_source_records=source_records,
            organization=organization,
            organization_reference_data=references,
        )

    def prepare_update_read_context(
        self,
        assessment_name: str,
        *,
        include_organization_reference_data: bool | None = None,
    ) -> UpdateReadContext:
        """Prepare UPDATE reads from the selected Assessment's existing rows."""
        assessment = self.get_assessment_for_update(assessment_name)
        questions = assessment.get("assessment_questions") or []
        template_name = assessment.get("assessment_template") or None
        template_source_rows: list[dict[str, Any]] = []
        if template_name:
            template = self.get_document("Assessment Template", template_name)
            template_source_rows = template.get("lookup_sources") or []

        lookup_links, source_records = self._resolve_lookup_sources(
            template_rows=template_source_rows,
            question_rows=questions,
        )
        categories = self.get_assessment_categories(questions)

        organization_name = None
        if assessment.get("reference_doctype") == "CRM Organization":
            organization_name = assessment.get("reference_document") or None
        elif assessment.get("document_type") == "CRM Organization":
            organization_name = assessment.get("document") or None
        organization = (
            self.get_organization(organization_name) if organization_name else None
        )
        should_read_references = include_organization_reference_data
        if should_read_references is None:
            should_read_references = organization is not None
        references = (
            self.get_organization_reference_data()
            if should_read_references
            else {}
        )
        return UpdateReadContext(
            assessment_operation="UPDATE",
            assessment=assessment,
            assessment_questions=questions,
            assessment_template_name=template_name,
            template_lookup_source_rows=template_source_rows,
            question_category_links=self.get_question_category_links(questions),
            assessment_categories=categories,
            lookup_source_links=lookup_links,
            lookup_source_records=source_records,
            organization=organization,
            organization_reference_data=references,
        )
