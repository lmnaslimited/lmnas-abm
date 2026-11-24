# Workflow direction

The unified workflow is a resumable coordinator over existing discovery and research package workflows. It records stage references and outcomes, while avoiding duplicate persistence for discovery history. CRM mutation stages use dry-run by default, explicit approval for writes, pre-create duplicate checks, audit records, and read-back verification. After partial Contact success, retry resolves the existing Contact before Lead sync.

Proposed sequence: resolve exact `org_id`; reuse organization research/assessment artifacts; run product assessments through existing orchestrator; identify and validate people; resolve/create Contact; resolve/create corresponding Lead; compile report. A stage should only be repeated if incomplete or explicitly requested. This is a design note, not an implemented command contract.
