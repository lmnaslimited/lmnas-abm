import unittest
from unittest.mock import Mock

from abm.crm.repository import CRMRepository


class CRMRepositoryTests(unittest.TestCase):
    def test_create_reads_template_with_embedded_questions(self):
        template = {
            "name": "template-1",
            "result_contract": "[]",
            "assessment_questions": [{"name": "template-row-1", "question": "Q?"}],
        }
        api = Mock()
        api.get_document.return_value = template
        repo = CRMRepository(api)

        result = repo.get_assessment_template_for_create("template-1")

        api.get_document.assert_called_once_with("Assessment Template", "template-1")
        self.assertEqual(result["assessment_questions"][0]["name"], "template-row-1")
        self.assertIn("result_contract", result)

    def test_update_reads_existing_assessment_with_its_child_rows(self):
        assessment = {
            "name": "CRM-ASS-1",
            "reference_doctype": "CRM Organization",
            "reference_document": "BEZ Transformátory",
            "assessment_questions": [{"name": "existing-row-1", "question": "Q?"}],
        }
        api = Mock()
        api.get_document.return_value = assessment
        repo = CRMRepository(api)

        result = repo.get_assessment_for_update("CRM-ASS-1")

        api.get_document.assert_called_once_with("CRM Assessment", "CRM-ASS-1")
        self.assertEqual(result["assessment_questions"][0]["name"], "existing-row-1")

    def test_get_organization_reference_data_uses_verified_link_targets(self):
        api = Mock()
        api.list_documents.side_effect = lambda doctype, **kwargs: [{"name": doctype}]
        repo = CRMRepository(api)

        result = repo.get_organization_reference_data()

        self.assertEqual(set(result), {"currency", "territory", "industry"})
        self.assertEqual(result["industry"], [{"name": "CRM Industry"}])
        self.assertEqual(api.list_documents.call_count, 3)

    def test_assessment_categories_are_deduplicated(self):
        api = Mock()
        api.get_document.side_effect = lambda doctype, name: {"doctype": doctype, "name": name}
        repo = CRMRepository(api)

        result = repo.get_assessment_categories([
            {"assessment_category": "Category A"},
            {"assessment_category": "Category A"},
            {"assessment_category": "Category B"},
            {},
        ])

        self.assertEqual(list(result), ["Category A", "Category B"])
        self.assertEqual(api.get_document.call_count, 2)

    def test_empty_lookup_fields_do_not_issue_requests(self):
        api = Mock()
        repo = CRMRepository(api)

        self.assertEqual(repo.get_lookup_sources_for_template({"lookup_sources": []}), [])
        api.get_document.assert_not_called()


if __name__ == "__main__":
    unittest.main()
