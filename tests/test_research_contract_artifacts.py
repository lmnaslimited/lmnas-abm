import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "workspace" / "proposals" / "research-instructions"


def fingerprint(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


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

    def test_both_stages_allow_empty_discovered_sources_and_reuse_ids(self):
        field = self.assessment["schema"]["properties"]["discovered_sources"]
        for stage in self.assessment["stages"]:
            self.assertIn(stage, ("DISCOVERY", "FULL_ASSESSMENT"))
            self.assertIsInstance([], list)
            self.assertEqual(len([]), 0)  # Empty array satisfies the array field; no minItems is imposed.
        evidence = self.assessment["schema"]["properties"]["question_results"]["items"]["properties"]["evidence_references"]
        evidence_id = evidence["items"]["properties"]["source_id"]
        self.assertEqual(evidence_id["type"], "string")
        rules = " ".join(self.assessment["validation_rules"]).lower()
        self.assertIn("same source_id", rules)
        self.assertIn("question_results[].evidence_references", rules)
        discovered = {"DISC-SRC-001": {"url": "https://example.org/report"}}
        cited_id = "DISC-SRC-001"
        self.assertIn(cited_id, discovered)
        self.assertIsInstance(field["items"]["properties"]["source_id"], dict)

    def test_existing_assessment_shapes_and_organization_contract_are_unchanged(self):
        # Fingerprints are from the pre-change repository contract snapshot.
        self.assertEqual(
            fingerprint(self.assessment["schema"]["properties"]["question_results"]),
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
