"""Orchestration interface placeholder for the Prepare → Collect → Confirm flow."""

from abm.cli import RunCommand


class RunOrchestrator:
    """Reserved for coordinating implemented adapters in a later milestone."""

    def prepare(self, command: RunCommand) -> None:
        raise NotImplementedError("Run orchestration is not implemented in the foundation milestone")
