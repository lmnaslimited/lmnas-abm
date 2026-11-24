# Data model direction

Canonical organization identity uses exact CRM Organization document name as `org_id`, with website/domain and source identity kept separately. Financial records retain reported amount, currency, unit/scale, normalized `revenue_usd_m`, rate, rate date/source, period, evidence, confidence and verification state. No conversion occurs for unknown currency or already normalized values.

Evidence records retain stable source ID, URL, publisher, retrieval/publication date, source type, supported claim and confidence. Contact records represent one person across product categories and include name, current title, organization, department, profile URL, verified business channels, role classification, product interests, evidence, confidence and verification status. CRM sync records retain identity key, Contact/Lead CRM IDs, per-document outcome, run/stage, timestamps and errors.

This document proposes Phase 2 models; existing persisted formats remain authoritative until migration is approved and specified.
