"""Assessment mapping interface placeholder."""


class AssessmentMapper:
    def map_results(self, questions: list[dict], results: list[dict]) -> list[dict]:
        raise NotImplementedError("Assessment mapping is not implemented")
