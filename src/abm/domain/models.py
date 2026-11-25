from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class Organization:
    org_id: str
    name: str
    website: str | None = None
    country: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FinancialInformation:
    reported_amount: Decimal
    currency: str | None
    scale: str
    revenue_usd_m: Decimal | None
    exchange_rate: Decimal | None = None
    rate_date: str | None = None
    source: str | None = None
    confidence: str | None = None


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    url: str
    title: str
    source_type: str
    claim_supported: str


@dataclass(frozen=True)
class AssessmentQuestion:
    row_id: str
    category: str
    question: str
    weightage: Decimal


@dataclass(frozen=True)
class AssessmentResponse:
    question_row_id: str
    ai_rating: Decimal
    ai_evidence_status: str
    ai_confidence: str
    ai_supporting_evidence: str
    evidence: tuple[EvidenceSource, ...] = ()


@dataclass(frozen=True)
class Assessment:
    assessment_id: str
    assessment_type: str
    template: str
    organization_id: str
    questions: tuple[AssessmentQuestion, ...]


@dataclass(frozen=True)
class CRMSynchronizationResult:
    doctype: str
    document_id: str
    status: str
    verified: bool
    fields_written: tuple[str, ...] = ()

