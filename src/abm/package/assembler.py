"""Package assembly interface placeholder; prompt and contract handling are deferred."""


class PackageAssembler:
    def assemble(self, configuration: dict, run_context: dict) -> dict:
        raise NotImplementedError("Package assembly is not implemented")
