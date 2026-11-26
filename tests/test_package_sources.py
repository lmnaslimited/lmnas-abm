import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from abm.crm.repository import CRMReadContextError, CRMRepository
from abm.package.assembler import PackageAssembler
from abm.package.preparation import ResearchPackagePreparer
from abm.package.source_resolver import resolve_sources


def source(name, territories=(), categories=(), disabled=0):
    return {"name": name, "source_name": name, "url": f"https://{name.lower()}.example",
            "disabled": disabled,
            "applicable_territories": [{"name": f"{name}-t{i}", "territory": t, "parent": name, "parentfield": "applicable_territories", "parenttype": "Assessment Lookup Source", "doctype": "Territories"} for i, t in enumerate(territories)],
            "applicable_assessment_categories": [{"name": f"{name}-c{i}", "assessment_category": c, "parent": name, "parentfield": "applicable_assessment_categories", "parenttype": "Assessment Lookup Source", "doctype": "Assessment Categories"} for i, c in enumerate(categories)]}


class SourceCatalogueTests(unittest.TestCase):
    def test_complete_catalogue_reads_all_pages_and_full_documents(self):
        api = Mock()
        api.list_documents.return_value = [{"name": "A", "disabled": 0}, {"name": "B", "disabled": 1}]
        docs = {"A": source("A", disabled=0), "B": source("B", disabled=1)}
        api.get_document.side_effect = lambda dt, name: docs[name] if dt == "Assessment Lookup Source" else {"name": name}
        catalogue = CRMRepository(api).get_source_catalogue(page_size=1)
        self.assertEqual(list(catalogue), ["A", "B"])
        api.list_documents.assert_called_once()
        self.assertEqual(api.list_documents.call_args.kwargs["page_size"], 1)
        self.assertEqual([call.args for call in api.get_document.call_args_list],
                         [("Assessment Lookup Source", "A"), ("Assessment Lookup Source", "B")])

    def test_catalogue_schema_and_reference_fail_closed(self):
        api = Mock()
        api.list_documents.return_value = [{"name": "A", "disabled": 0}]
        api.get_document.side_effect = lambda dt, name: source("A", territories=["T"] if dt == "Assessment Lookup Source" else ()) if dt == "Assessment Lookup Source" else {"name": "wrong"}
        with self.assertRaisesRegex(CRMReadContextError, "missing CRM Territory"):
            CRMRepository(api).get_source_catalogue()


class TerritoryResolutionTests(unittest.TestCase):
    territories = {
        "Region": {"name": "Region", "parent_crm_territory": None, "lft": 1},
        "CountryA": {"name": "CountryA", "parent_crm_territory": "Region", "lft": 2},
        "Subdivision": {"name": "Subdivision", "parent_crm_territory": "CountryA", "lft": 2.5},
        "CountryB": {"name": "CountryB", "parent_crm_territory": "Region", "lft": 3},
        "OtherRegion": {"name": "OtherRegion", "parent_crm_territory": None, "lft": 4},
        "Sibling": {"name": "Sibling", "parent_crm_territory": "OtherRegion", "lft": 5},
    }

    def test_region_phases_and_scope_exclusion(self):
        cat = {"G": source("G"), "R": source("R", ["Region"]), "A": source("A", ["CountryA"]),
               "D": source("D", ["Subdivision"]), "B": source("B", ["CountryB"]), "X": source("X", ["Sibling"])}
        result = resolve_sources(cat, self.territories, run_territory="Region", scope_type="region", questions=[])
        self.assertEqual([(p["phase"], p["source_ids"]) for p in result["phases"]],
                         [("global", ["G"]), ("regional", ["R"]), ("regional_descendants", ["A", "D", "B"])])

    def test_country_exact_parent_global_order_and_no_siblings(self):
        cat = {"G": source("G"), "R": source("R", ["Region"]), "A": source("A", ["CountryA"]),
               "B": source("B", ["CountryB"])}
        result = resolve_sources(cat, self.territories, run_territory="CountryA", scope_type="country", questions=[])
        self.assertEqual([p["source_ids"] for p in result["phases"]], [["A"], ["R"], ["G"]])
        self.assertNotIn("B", sum((p["source_ids"] for p in result["phases"]), []))

    def test_category_generic_multi_category_and_explicit_associations(self):
        cat = {"G": source("G"), "C": source("C", categories=["CAT1", "CAT2"]),
               "E": source("E", categories=["CAT2"]), "QE": source("QE", categories=["OTHER"])}
        links = [
            {"location": "template.lookup_sources", "lookup_source": "E", "child_row_name": "tpl-row", "child_row_idx": 1},
            {"location": "assessment_questions[].additional_lookup_sources", "question_row_name": "q1",
             "lookup_source": "QE", "child_row_name": "q-row", "child_row_idx": 3},
        ]
        questions = [{"name": "q1", "assessment_category": "CAT1"}, {"name": "q2", "assessment_category": "CAT2"}]
        result = resolve_sources(cat, self.territories, run_territory="CountryA", scope_type="country", questions=questions, explicit_links=links)
        self.assertEqual(result["generic_source_ids"], ["G"])
        self.assertEqual(result["question_sources"], {"q1": ["QE", "E", "C"], "q2": ["E", "C"]})
        self.assertEqual(result["explicit_associations"][1]["child_row_name"], "q-row")

    def test_only_matching_categories_or_valid_explicit_links_qualify(self):
        cat = {
            "GENERIC": source("GENERIC"),
            "MATCH": source("MATCH", categories=["CAT1", "UNUSED"]),
            "UNMATCHED": source("UNMATCHED", categories=["UNUSED"]),
            "EXPLICIT": source("EXPLICIT", ["CountryA"], ["UNUSED"]),
            "OUTSIDE": source("OUTSIDE", ["CountryB"], ["UNUSED"]),
        }
        explicit = [
            {"location": "template.lookup_sources", "lookup_source": "EXPLICIT"},
            {"location": "template.lookup_sources", "lookup_source": "OUTSIDE"},
        ]
        result = resolve_sources(
            cat, self.territories, run_territory="CountryA", scope_type="country",
            questions=[{"name": "q1", "assessment_category": "CAT1"}],
            explicit_links=explicit,
        )
        assigned = {sid for phase in result["phases"] for sid in phase["source_ids"]}
        self.assertEqual(assigned, {"GENERIC", "MATCH", "EXPLICIT"})
        self.assertEqual(set(result["category_sources"]), {"CAT1"})
        self.assertEqual(result["category_sources"], {"CAT1": ["MATCH"]})
        self.assertEqual(result["source_selection"]["UNMATCHED"]["reason"], "category_not_applicable")
        self.assertIn("EXPLICIT", result["question_sources"]["q1"])
        self.assertNotIn("OUTSIDE", result["question_sources"]["q1"])

    def test_shared_parent_descendant_source_appears_in_earliest_phase_only(self):
        shared = source("SHARED", ["Region", "CountryA"])
        result = resolve_sources({"SHARED": shared}, self.territories, run_territory="Region", scope_type="region", questions=[])
        self.assertEqual([p["source_ids"] for p in result["phases"]], [[], ["SHARED"], []])
        self.assertEqual(result["source_selection"]["SHARED"]["applicable_territories"], ["Region", "CountryA"])

    def test_explicit_source_still_requires_territory_match(self):
        cat = {"SIBLING": source("SIBLING", ["CountryB"])}
        explicit = [{"location": "template.lookup_sources", "lookup_source": "SIBLING"}]
        result = resolve_sources(cat, self.territories, run_territory="CountryA", scope_type="country", questions=[{"name": "q", "assessment_category": "C"}], explicit_links=explicit)
        self.assertEqual(result["question_sources"]["q"], [])


class PackageTests(unittest.TestCase):
    def test_package_prompt_contract_bytes_checksums_and_determinism(self):
        config = {"assessment_template": {"name": "T", "master_prompt": " exact\n", "result_contract": '{"a": 1}', "assessment_questions": []},
                  "source_catalogue": {}, "research_plan": {}}
        with tempfile.TemporaryDirectory() as tmp:
            one = PackageAssembler().assemble(config, {"territory": "R"}, output_dir=Path(tmp) / "one")
            two = PackageAssembler().assemble(config, {"territory": "R"})
            self.assertEqual(one["files"], two["files"])
            self.assertEqual(one["files"]["master_prompt.md"], b" exact\n")
            self.assertEqual(one["files"]["result_contract.json"], b'{"a": 1}')
            checksums = json.loads(one["files"]["checksums.json"])
            self.assertEqual(checksums["master_prompt.md"], hashlib.sha256(b" exact\n").hexdigest())
            self.assertTrue((Path(tmp) / "one" / "manifest.json").exists())
            archive = Path(tmp) / "one" / "one.zip"
            self.assertTrue(archive.is_file())
            PackageAssembler.verify_archive(archive, one["files"])

    def test_projection_and_organization_exclusions_keep_only_review_fields(self):
        config = {"assessment_template": {
            "name": "T", "doctype": "Assessment Template", "master_prompt": "p",
            "result_contract": "{}", "owner": "secret", "assessment_questions": []},
            "assessment_questions": [{"name": "q", "idx": 4, "question": "Q",
                "assessment_category": "C", "mandatory": 1, "ai_rating": 5,
                "creation": "now", "ai_prompt_instructions": "instructions"}],
            "source_catalogue": {"S": source("S")}, "organization_exclusions": [
                {"crm_organization_id": "O", "organization_name": "Org", "url": None}],
            "research_plan": {}}
        package = PackageAssembler().assemble(config, {})
        template = json.loads(package["files"]["template_snapshot.json"])
        question = json.loads(package["files"]["questions.json"])[0]
        source_doc = json.loads(package["files"]["source_catalogue.json"])["S"]
        self.assertNotIn("owner", template)
        self.assertNotIn("assessment_questions", template)
        self.assertNotIn("ai_rating", question)
        self.assertNotIn("idx", question)
        self.assertEqual(question["question"], "Q")
        self.assertEqual(source_doc["applicable_territories"], [])
        self.assertEqual(json.loads(package["files"]["organization_exclusions.json"])[0]["url"], None)

    def test_preparation_composes_live_context_catalogue_territory_and_plan(self):
        template = {"name": "T", "document_type": "CRM Organization", "master_prompt": "P",
                    "result_contract": "{}", "assessment_questions": [{"name": "q", "assessment_category": "CAT"}],
                    "lookup_sources": [{"name": "template-link-row", "idx": 1, "lookup_source": "EXPLICIT"}]}
        master = source("EXPLICIT", ["Region"], ["TENDER ONLY"])
        context = type("Context", (), {"assessment_template": template,
            "assessment_questions": template["assessment_questions"], "organization": None,
            "lookup_source_links": [{"location": "template.lookup_sources", "question_row_name": None,
                "child_row_name": "template-link-row", "child_row_idx": 1, "lookup_source": "EXPLICIT",
                "child_row": template["lookup_sources"][0]}], "lookup_source_records": {"EXPLICIT": master}})()
        repo = Mock()
        repo.prepare_create_read_context.return_value = context
        catalogue = {
            "EXPLICIT": master, "GEN": source("GEN"), "OUT": source("OUT", ["Sibling"]),
            "Tenders Electronic Daily (TED) - EU Public Procurement": source(
                "Tenders Electronic Daily (TED) - EU Public Procurement", ["Region"], ["Tender - Procurement"]
            ),
            "Slovakia UVO - Public Procurement Portal": source(
                "Slovakia UVO - Public Procurement Portal", ["Country"], ["Tender - Procurement"]
            ),
        }
        catalogue.update({f"OTHER-{index:03d}": source(f"OTHER-{index:03d}", categories=["Tender - Procurement"])
                          for index in range(1, 52)})
        self.assertEqual(len(catalogue), 56)
        repo.get_source_catalogue.return_value = catalogue
        repo.list_documents.return_value = [
            {"name": "Region", "parent_crm_territory": None, "lft": 1, "rgt": 4, "is_group": 1},
            {"name": "Country", "parent_crm_territory": "Region", "lft": 2, "rgt": 3, "is_group": 0},
            {"name": "OtherRegion", "parent_crm_territory": None, "lft": 5, "rgt": 8, "is_group": 1},
            {"name": "Sibling", "parent_crm_territory": "OtherRegion", "lft": 6, "rgt": 7, "is_group": 0},
        ]
        prepared = ResearchPackagePreparer(repo).prepare_create("T", {}, run_territory="Region")
        plan = json.loads(prepared["files"]["research_plan.json"])
        self.assertEqual(plan["phases"][1]["source_ids"], ["EXPLICIT"])
        self.assertEqual(plan["template_explicit_source_ids"], ["EXPLICIT"])
        self.assertEqual(plan["question_categories"], {"q": "CAT"})
        catalogue = json.loads(prepared["files"]["source_catalogue.json"])
        self.assertEqual(len(catalogue), 56)
        self.assertIn("Tenders Electronic Daily (TED) - EU Public Procurement", catalogue)
        self.assertIn("Slovakia UVO - Public Procurement Portal", catalogue)
        assigned = {sid for phase in plan["phases"] for sid in phase["source_ids"]}
        self.assertEqual(assigned, {"EXPLICIT", "GEN"})
        self.assertLessEqual(set(plan["category_sources"]), {"CAT"})
        self.assertNotIn("TENDER ONLY", plan["category_sources"])
        self.assertEqual(plan["unassigned_sources"]["Tenders Electronic Daily (TED) - EU Public Procurement"],
                         "category_not_applicable")
        self.assertEqual(plan["unassigned_sources"]["Slovakia UVO - Public Procurement Portal"],
                         "category_not_applicable")
        self.assertEqual(prepared["preparation_summary"], {
            "catalogue_retrieved": 56, "applicable_selected": 2, "excluded": 54,
            "organizations_retrieved": 4, "organization_exclusions": 4,
            "phase_counts": [
                {"phase": "global", "territory": None, "source_count": 1},
                {"phase": "regional", "territory": "Region", "source_count": 1},
                {"phase": "regional_descendants", "territory": ["Country"], "source_count": 0},
            ],
        })

    def test_existing_package_directory_is_not_overwritten(self):
        config = {"assessment_template": {"master_prompt": "p", "result_contract": "{}"}}
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "existing"
            target.mkdir()
            (target / "keep.txt").write_text("keep")
            with self.assertRaises(FileExistsError):
                PackageAssembler().assemble(config, {}, output_dir=target)
            self.assertEqual((target / "keep.txt").read_text(), "keep")

    def test_zip_is_inside_package_directory(self):
        config = {"assessment_template": {"master_prompt": "p", "result_contract": "{}"}}
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "run.part"
            PackageAssembler().assemble(config, {}, output_dir=target)
            self.assertTrue((target / "run.part.zip").is_file())
            with __import__("zipfile").ZipFile(target / "run.part.zip") as archive:
                self.assertNotIn("run.part.zip", archive.namelist())
                self.assertIn("manifest.json", archive.namelist())

    def test_preparer_rejects_unknown_regional_territory(self):
        context = type("Context", (), {"assessment_template": {"name": "T", "master_prompt": "p",
            "result_contract": "{}", "assessment_questions": []}, "assessment_questions": [],
            "organization": None, "lookup_source_links": [], "lookup_source_records": {}})()
        repo = Mock()
        repo.prepare_create_read_context.return_value = context
        repo.get_source_catalogue.return_value = {}
        repo.list_documents.return_value = []
        with self.assertRaisesRegex(ValueError, "does not exist"):
            ResearchPackagePreparer(repo).prepare_create("T", {}, run_territory="Missing")


if __name__ == "__main__":
    unittest.main()
