"""Contract validator interface placeholder."""


class ContractValidator:
    def validate(self, response: dict, output_contract: dict) -> dict:
        raise NotImplementedError("Output validation is not implemented")
