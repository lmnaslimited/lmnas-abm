import unittest
from unittest.mock import Mock

from abm.crm.client import FrappeAPIError
from abm.crm.repository import CRMReadContextError, CRMRepository


def valid_source_master(name, source_name=None, url=None, **extra):
    return {
        "name": name, "source_name": source_name or name,
        "url": url or f"https://{name.lower()}.example", "disabled": 0,
        "applicable_territories": [], "applicable_assessment_categories": [], **extra,
    }


class CRMRepositoryTests(unittest.TestCase):
    def test_create_context_preserves_rows_and_enriches_distinct_masters(self):
        template_source_1 = {"name": "template-source-row-1", "idx": 1, "lookup_source": "SRC-A", "custom": "kept"}
        template_source_2 = {"name": "template-source-row-2", "idx": 2, "lookup_source": "SRC-A"}
        question_source_1 = {"name": "question-source-row-1", "idx": 1, "lookup_source": "SRC-B"}
        question_source_2 = {"name": "question-source-row-2", "idx": 2, "lookup_source": "SRC-A"}
        q1 = {
            "name": "template-question-1", "idx": 1,
            "assessment_category": "Category A",
            "additional_lookup_sources": [question_source_1, question_source_2],
        }
        q2 = {
            "name": "template-question-2", "idx": 2,
            "assessment_category": "Category B",
            "additional_lookup_sources": [],
        }
        template = {
            "name": "T-1", "document_type": "CRM Organization",
            "result_contract": "{}", "lookup_sources": [template_source_1, template_source_2],
            "assessment_questions": [q1, q2],
        }
        masters = {
            "SRC-A": valid_source_master("SRC-A", "Source A", "https://a.example"),
            "SRC-B": valid_source_master("SRC-B", "Source B", "https://b.example"),
        }
        api = Mock()
        api.get_document.side_effect = lambda doctype, name: (
            template if doctype == "Assessment Template" else
            masters[name] if doctype == "Assessment Lookup Source" else
            {"name": name, "doctype": doctype}
        )
        repo = CRMRepository(api)

        context = repo.prepare_create_read_context(
            "T-1", include_organization_reference_data=False
        )

        self.assertEqual(context.assessment_operation, "CREATE")
        self.assertIs(context.assessment_template["lookup_sources"][0], template_source_1)
        self.assertIs(context.assessment_questions[0], q1)
        self.assertEqual(
            [(link["location"], link["question_row_name"], link["child_row_name"], link["lookup_source"])
             for link in context.lookup_source_links],
            [
                ("template.lookup_sources", None, "template-source-row-1", "SRC-A"),
                ("template.lookup_sources", None, "template-source-row-2", "SRC-A"),
                ("assessment_questions[].additional_lookup_sources", "template-question-1", "question-source-row-1", "SRC-B"),
                ("assessment_questions[].additional_lookup_sources", "template-question-1", "question-source-row-2", "SRC-A"),
            ],
        )
        self.assertIs(context.lookup_source_links[0]["child_row"], template_source_1)
        self.assertEqual(context.lookup_source_records["SRC-A"]["url"], "https://a.example")
        self.assertEqual(context.lookup_source_records["SRC-B"]["url"], "https://b.example")
        self.assertEqual(set(context.assessment_categories), {"Category A", "Category B"})
        self.assertEqual(context.question_category_links[0]["question_row_name"], "template-question-1")
        self.assertEqual(context.question_category_links[1]["question_idx"], 2)
        source_calls = [
            call.args for call in api.get_document.call_args_list
            if call.args[0] == "Assessment Lookup Source"
        ]
        self.assertCountEqual(source_calls, [("Assessment Lookup Source", "SRC-A"), ("Assessment Lookup Source", "SRC-B")])
        self.assertEqual(len(source_calls), 2)  # duplicate SRC-A rows resolved once
        self.assertFalse(any(args[0] == "Assessment Lookup Sources" for args in api.get_document.call_args_list))
        api.list_documents.assert_not_called()

    def test_update_context_uses_existing_questions_and_template_level_lookup_rows(self):
        template_child = {"name": "template-child", "idx": 1, "lookup_source": "SHARED"}
        assessment_child = {"name": "assessment-child", "idx": 1, "lookup_source": "SHARED", "custom": "kept"}
        assessment_question = {
            "name": "existing-question-row", "idx": 3,
            "assessment_category": "Existing Category",
            "additional_lookup_sources": [assessment_child],
        }
        assessment = {
            "name": "A-1", "assessment_template": "T-1",
            "reference_doctype": "CRM Organization", "reference_document": "Org-1",
            "assessment_questions": [assessment_question],
        }
        template_question = {
            "name": "template-question-should-not-be-used", "idx": 1,
            "additional_lookup_sources": [{"name": "ignored-row", "lookup_source": "UNUSED"}],
        }
        template = {
            "name": "T-1", "lookup_sources": [template_child],
            "assessment_questions": [template_question],
        }
        master = valid_source_master("SHARED", "SHARED", "https://shared.example")
        api = Mock()
        api.get_document.side_effect = lambda doctype, name: {
            ("CRM Assessment", "A-1"): assessment,
            ("Assessment Template", "T-1"): template,
            ("Assessment Lookup Source", "SHARED"): master,
            ("Assessment Category", "Existing Category"): {"name": "Existing Category"},
            ("CRM Organization", "Org-1"): {"name": "Org-1"},
        }[(doctype, name)]
        repo = CRMRepository(api)

        context = repo.prepare_update_read_context(
            "A-1", include_organization_reference_data=False
        )

        self.assertEqual(context.assessment_operation, "UPDATE")
        self.assertIs(context.assessment_questions[0], assessment_question)
        self.assertEqual(context.assessment_questions[0]["name"], "existing-question-row")
        self.assertEqual(context.template_lookup_source_rows, [template_child])
        self.assertEqual([row["lookup_source"] for row in context.lookup_source_links], ["SHARED", "SHARED"])
        self.assertEqual([row["child_row_name"] for row in context.lookup_source_links], ["template-child", "assessment-child"])
        self.assertEqual(context.lookup_source_records["SHARED"]["url"], "https://shared.example")
        self.assertEqual(context.organization, {"name": "Org-1"})
        self.assertEqual(context.question_category_links, [{
            "question_row_name": "existing-question-row",
            "question_idx": 3,
            "assessment_category": "Existing Category",
        }])
        source_calls = [call.args for call in api.get_document.call_args_list if call.args[0] == "Assessment Lookup Source"]
        self.assertEqual(source_calls, [("Assessment Lookup Source", "SHARED")])
        self.assertFalse(any(args[0] == "Assessment Lookup Sources" for args in api.get_document.call_args_list))
        self.assertFalse(any(args[1] == "UNUSED" for args in api.get_document.call_args_list))
        api.list_documents.assert_not_called()

    def test_create_context_fetches_template_questions_and_reference_data(self):
        template = {
            "name": "T-ORG", "document_type": "CRM Organization",
            "assessment_questions": [{"name": "q-1", "assessment_category": "Cat"}],
            "lookup_sources": [],
        }
        api = Mock()
        api.get_document.side_effect = lambda doctype, name: template if doctype == "Assessment Template" else {"name": name}
        api.list_documents.side_effect = lambda doctype, **kwargs: [{"name": doctype}]
        repo = CRMRepository(api)

        context = repo.prepare_create_read_context("T-ORG")

        self.assertEqual(context.organization_reference_data, {
            "currency": [{"name": "Currency"}],
            "territory": [{"name": "CRM Territory"}],
            "industry": [{"name": "CRM Industry"}],
        })
        self.assertEqual(api.list_documents.call_count, 3)

    def test_create_context_can_fetch_existing_organization(self):
        template = {"name": "T-PRODUCT", "document_type": "CRM Product", "assessment_questions": []}
        api = Mock()
        api.get_document.side_effect = lambda doctype, name: template if doctype == "Assessment Template" else {"name": name}
        repo = CRMRepository(api)

        context = repo.prepare_create_read_context("T-PRODUCT", organization_name="Org-1")

        self.assertEqual(context.organization, {"name": "Org-1"})
        self.assertEqual(context.organization_reference_data, {})
        api.get_document.assert_any_call("CRM Organization", "Org-1")
        api.list_documents.assert_not_called()

    def test_missing_source_master_fails_context_with_safe_error(self):
        template = {
            "name": "T-1", "assessment_questions": [],
            "lookup_sources": [{"name": "child-1", "lookup_source": "MISSING"}],
        }
        api = Mock()
        api.get_document.side_effect = lambda doctype, name: (
            template if doctype == "Assessment Template" else
            (_ for _ in ()).throw(FrappeAPIError("generic request failed"))
        )
        repo = CRMRepository(api)

        with self.assertRaisesRegex(CRMReadContextError, "MISSING.*could not be retrieved"):
            repo.prepare_create_read_context("T-1", include_organization_reference_data=False)
        self.assertEqual(api.get_document.call_args_list[-1].args, ("Assessment Lookup Source", "MISSING"))

    def test_disabled_explicit_source_fails_context(self):
        template = {"name": "T-1", "assessment_questions": [],
                    "lookup_sources": [{"name": "child-1", "lookup_source": "DISABLED"}]}
        api = Mock()
        api.get_document.side_effect = lambda doctype, name: (
            template if doctype == "Assessment Template" else
            valid_source_master("DISABLED", disabled=1)
        )
        with self.assertRaisesRegex(CRMReadContextError, "DISABLED.*disabled"):
            CRMRepository(api).prepare_create_read_context("T-1", include_organization_reference_data=False)

    def test_source_master_without_url_fails_context(self):
        template = {
            "name": "T-1", "assessment_questions": [],
            "lookup_sources": [{"name": "child-1", "lookup_source": "NO-URL"}],
        }
        api = Mock()
        api.get_document.side_effect = lambda doctype, name: (
            template if doctype == "Assessment Template" else {"name": name, "source_name": name}
        )
        repo = CRMRepository(api)

        with self.assertRaisesRegex(CRMReadContextError, "NO-URL.*no usable URL"):
            repo.prepare_create_read_context("T-1", include_organization_reference_data=False)

    def test_source_master_without_source_name_is_incomplete(self):
        template = {
            "name": "T-1", "assessment_questions": [],
            "lookup_sources": [{"name": "child-1", "lookup_source": "NO-NAME"}],
        }
        api = Mock()
        api.get_document.side_effect = lambda doctype, name: (
            template if doctype == "Assessment Template" else {"name": name, "url": "https://source.example"}
        )
        repo = CRMRepository(api)

        with self.assertRaisesRegex(CRMReadContextError, "NO-NAME.*no source_name metadata"):
            repo.prepare_create_read_context("T-1", include_organization_reference_data=False)

    def test_source_child_row_without_link_fails_context(self):
        template = {
            "name": "T-1", "assessment_questions": [],
            "lookup_sources": [{"name": "broken-child", "idx": 1}],
        }
        api = Mock()
        api.get_document.return_value = template
        repo = CRMRepository(api)

        with self.assertRaisesRegex(CRMReadContextError, "broken-child.*no lookup_source"):
            repo.prepare_create_read_context("T-1", include_organization_reference_data=False)
        api.get_document.assert_called_once_with("Assessment Template", "T-1")

    def test_unreferenced_source_masters_are_never_retrieved(self):
        template = {
            "name": "T-1", "assessment_questions": [],
            "lookup_sources": [{"name": "child-1", "idx": 1, "lookup_source": "USED"}],
        }
        api = Mock()
        api.get_document.side_effect = lambda doctype, name: (
            template if doctype == "Assessment Template" else
            valid_source_master("USED", "USED", "https://used.example")
        )
        repo = CRMRepository(api)

        context = repo.prepare_create_read_context("T-1", include_organization_reference_data=False)

        self.assertEqual(set(context.lookup_source_records), {"USED"})
        self.assertEqual(
            [call.args for call in api.get_document.call_args_list if call.args[0] == "Assessment Lookup Source"],
            [("Assessment Lookup Source", "USED")],
        )

    def test_category_links_preserve_question_identity_and_order(self):
        api = Mock()
        api.get_document.side_effect = lambda doctype, name: {"doctype": doctype, "name": name}
        repo = CRMRepository(api)
        questions = [
            {"name": "q-second", "idx": 8, "assessment_category": "Category A"},
            {"name": "q-first", "idx": 3, "assessment_category": "Category A"},
        ]

        categories = repo.get_assessment_categories(questions)
        links = repo.get_question_category_links(questions)

        self.assertEqual(list(categories), ["Category A"])
        self.assertEqual([link["question_row_name"] for link in links], ["q-second", "q-first"])
        self.assertEqual([link["question_idx"] for link in links], [8, 3])
        self.assertEqual(api.get_document.call_count, 1)

    def test_reference_data_can_include_additional_verified_link_targets(self):
        api = Mock()
        api.list_documents.side_effect = lambda doctype, **kwargs: [{"name": doctype}]
        repo = CRMRepository(api)

        result = repo.get_organization_reference_data({"account_manager": "User"})

        self.assertEqual(set(result), {"currency", "territory", "industry", "account_manager"})
        self.assertEqual(result["account_manager"], [{"name": "User"}])
        self.assertEqual(api.list_documents.call_count, 4)

    def test_empty_lookup_rows_do_not_make_master_requests(self):
        api = Mock()
        repo = CRMRepository(api)

        self.assertEqual(repo.get_lookup_sources_for_template({"lookup_sources": []}), {})
        api.get_document.assert_not_called()
        api.list_documents.assert_not_called()


if __name__ == "__main__":
    unittest.main()
