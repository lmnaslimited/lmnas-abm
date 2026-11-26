import hashlib
import json
import re
import unittest
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "workspace" / "proposals" / "research-instructions"


def fingerprint(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def assert_schema_valid(test_case, instance, schema, path="$"):
    """Check the JSON Schema keywords used by this repository contract.

    The project has no JSON Schema validation dependency, so this focused
    test helper interprets the schema's type, required, properties, items,
    const, enum, pattern, and URI format keywords.
    """
    expected_type = schema.get("type")
    expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
    type_checks = {
        "object": lambda value: isinstance(value, dict),
        "array": lambda value: isinstance(value, list),
        "string": lambda value: isinstance(value, str),
        "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": lambda value: isinstance(value, bool),
        "null": lambda value: value is None,
    }
    if expected_type is not None:
        test_case.assertTrue(
            any(type_checks[kind](instance) for kind in expected_types),
            f"{path}: expected {expected_types}, got {type(instance).__name__}",
        )
    if "const" in schema:
        test_case.assertEqual(instance, schema["const"], f"{path}: const mismatch")
    if "enum" in schema:
        test_case.assertIn(instance, schema["enum"], f"{path}: enum mismatch")
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            test_case.assertIn(key, instance, f"{path}: missing required property {key!r}")
        for key, subschema in schema.get("properties", {}).items():
            if key in instance:
                assert_schema_valid(test_case, instance[key], subschema, f"{path}.{key}")
    if isinstance(instance, list) and "items" in schema:
        for index, item in enumerate(instance):
            assert_schema_valid(test_case, item, schema["items"], f"{path}[{index}]")
    if isinstance(instance, str):
        if "pattern" in schema:
            test_case.assertRegex(instance, re.compile(schema["pattern"]), f"{path}: pattern mismatch")
        if schema.get("format") == "uri":
            parsed = urlsplit(instance)
            test_case.assertTrue(parsed.scheme and parsed.netloc, f"{path}: invalid URI")


def _assessment_response(stage, discovered_sources):
    return {
        "contract_type": "ASSESSMENT",
        "contract_version": "1.1",
        "assessment_stage": stage,
        "subject": {"organization_name": "Example Transformer GmbH"},
        "question_results": [{
            "question_id": "question-row-1",
            "assessment_category": "ORG - Manufacturing Footprint",
            "question": "Does the organization operate transformer manufacturing facilities?",
            "ai_rating": None,
            "ai_evidence_status": "Insufficient",
            "ai_confidence": "Low",
            "ai_supporting_evidence": "Insufficient public evidence was found.",
            "evidence_references": [],
        }],
        "stage_summary": {
            "overall_finding": "Initial research summary.",
            "mandatory_negative_found": False,
            "insufficient_evidence_questions": ["question-row-1"],
            "limitations": [],
        },
        "discovered_sources": discovered_sources,
    }


class ResearchContractArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contracts = json.loads((PROPOSAL / "result_contract.json").read_text())
        cls.assessment = next(x for x in cls.contracts if x["contract_type"] == "ASSESSMENT")
        cls.organization = next(x for x in cls.contracts if x["contract_type"] == "ORGANIZATION")
        cls.prompt = (PROPOSAL / "master_prompt.md").read_text()

    def test_discovered_sources_is_required_and_typed(self):
        contract = self.assessment
        self.assertEqual(contract["contract_version"], "1.1")
        self.assertEqual(contract["schema"]["properties"]["contract_version"]["const"], "1.1")
        self.assertIn("discovered_sources", contract["schema"]["required"])
        field = contract["schema"]["properties"]["discovered_sources"]
        self.assertEqual(field["type"], "array")
        self.assertFalse(field.get("minItems", 0))
        item = field["items"]
        self.assertEqual(set(item["required"]), {
            "source_id", "source_name", "url", "publisher", "applicable_territories",
            "applicable_assessment_categories", "relevance",
        })
        self.assertEqual(item["properties"]["publisher"]["type"], ["string", "null"])
        self.assertEqual(item["properties"]["url"]["format"], "uri")

    def test_assessment_contract_question_references_use_questions_artifact(self):
        contract = self.assessment
        text = json.dumps({
            "description": contract.get("description"),
            "schema": contract["schema"],
            "validation_rules": contract["validation_rules"],
        })
        self.assertNotIn("assessment_template.json", text)
        self.assertIn("questions.json", text)

    def test_assessment_outputs_validate_for_empty_and_populated_discovered_sources(self):
        schema = self.assessment["schema"]
        source = {
            "source_id": "DISC-SRC-001",
            "source_name": "Example Research Report",
            "url": "https://example.org/reports/transformers",
            "publisher": "Example Research Institute",
            "applicable_territories": ["Germany"],
            "applicable_assessment_categories": ["ORG - Manufacturing Footprint"],
            "relevance": "Provides current manufacturing capacity analysis.",
        }
        for stage in ("DISCOVERY", "FULL_ASSESSMENT"):
            with self.subTest(stage=stage, discovered_sources="empty"):
                response = _assessment_response(stage, [])
                assert_schema_valid(self, response, schema)

            with self.subTest(stage=stage, discovered_sources="populated"):
                response = _assessment_response(stage, [source])
                response["question_results"][0]["evidence_references"].append({
                    "source_id": source["source_id"],
                    "url": source["url"],
                    "relevance": "Supports the manufacturing-footprint finding.",
                })
                assert_schema_valid(self, response, schema)
                self.assertEqual(
                    response["discovered_sources"][0]["source_id"],
                    response["question_results"][0]["evidence_references"][0]["source_id"],
                )

        invalid_sources = [
            {key: value for key, value in source.items() if key != "publisher"},
            {**source, "source_id": "TEMP-1"},
            {**source, "url": "not a URL"},
            {**source, "applicable_territories": "Germany"},
            {**source, "applicable_assessment_categories": [None]},
        ]
        for invalid in invalid_sources:
            with self.subTest(invalid=invalid):
                response = _assessment_response("DISCOVERY", [invalid])
                with self.assertRaises(AssertionError):
                    assert_schema_valid(self, response, schema)

    def test_existing_assessment_shapes_and_organization_contract_are_unchanged(self):
        # Fingerprints are from the pre-change repository contract snapshot.
        def restore_old_artifact_name(value):
            if isinstance(value, str):
                return value.replace("questions.json", "assessment_template.json")
            if isinstance(value, list):
                return [restore_old_artifact_name(item) for item in value]
            if isinstance(value, dict):
                return {key: restore_old_artifact_name(item) for key, item in value.items()}
            return value

        self.assertEqual(
            fingerprint(restore_old_artifact_name(
                self.assessment["schema"]["properties"]["question_results"]
            )),
            "a3b820216fc49c7d3a62e3868cbb10e8e8bed90770635e21ca9e719e4ddf3b7e",
        )
        self.assertEqual(
            fingerprint(self.assessment["schema"]["properties"]["stage_summary"]),
            "3938c81238425941d49d904f15771e478c2e8f620e116c6ee3ac1fae2fa01722",
        )
        self.assertEqual(
            fingerprint(self.organization),
            "bbc7c6561dd9fa3a86f4ad9e264f31d544568b47d56dc8535218351278e67898",
        )
        self.assertEqual(self.assessment["stages"], ["DISCOVERY", "FULL_ASSESSMENT"])
        self.assertEqual(
            [key for key in self.assessment["schema"]["required"] if key != "discovered_sources"],
            ["contract_type", "contract_version", "assessment_stage", "subject", "question_results", "stage_summary"],
        )

    def test_html_prompt_has_concise_discovered_source_instruction(self):
        self.assertTrue(self.prompt.startswith('<div class="ql-editor read-mode">'))
        self.assertTrue(self.prompt.rstrip().endswith("</div>"))
        self.assertIn("<h2>12. Result requirements</h2>", self.prompt)
        self.assertIn("Populate `discovered_sources` as defined in `result_contract.json` for both assessment stages.", self.prompt)
        self.assertIn("absent from the complete `source_catalogue.json` (not merely the selected `research_plan.json`)", self.prompt)
        self.assertIn("deduplicate by canonical URL", self.prompt)
        self.assertIn("exact CRM Territory and Assessment Category identities", self.prompt)
        self.assertIn("same temporary `source_id` in `question_results[].evidence_references`", self.prompt)
        self.assertIn("Return an empty array when none qualify.", self.prompt)


if __name__ == "__main__":
    unittest.main()
