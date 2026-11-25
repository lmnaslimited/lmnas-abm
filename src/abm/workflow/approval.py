"""Approval interface placeholder; CRM workflow states must be inspected first."""


class ApprovalWorkflow:
    def confirm(self, staged_results: dict) -> dict:
        raise NotImplementedError("Approval workflow is not implemented")
