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
        self.assertEqual(list(catalogue), ["A"])
        api.list_documents.assert_called_once()
        self.assertEqual(api.list_documents.call_args.kwargs["page_size"], 1)
        self.assertEqual(api.get_document.call_args_list[0].args, ("Assessment Lookup Source", "A"))

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
        "CountryB": {"name": "CountryB", "parent_crm_territory": "Region", "lft": 3},
        "OtherRegion": {"name": "OtherRegion", "parent_crm_territory": None, "lft": 4},
        "Sibling": {"name": "Sibling", "parent_crm_territory": "OtherRegion", "lft": 5},
    }

    def test_region_phases_and_scope_exclusion(self):
        cat = {"G": source("G"), "R": source("R", ["Region"]), "A": source("A", ["CountryA"]),
               "B": source("B", ["CountryB"]), "X": source("X", ["Sibling"])}
        result = resolve_sources(cat, self.territories, run_territory="Region", scope_type="region", questions=[])
        self.assertEqual([(p["phase"], p["source_ids"]) for p in result["phases"]],
                         [("global", ["G"]), ("regional", ["R"]), ("country", ["A"]), ("country", ["B"])])

    def test_country_exact_parent_global_order_and_no_siblings(self):
        cat = {"G": source("G"), "R": source("R", ["Region"]), "A": source("A", ["CountryA"]),
               "B": source("B", ["CountryB"])}
        result = resolve_sources(cat, self.territories, run_territory="CountryA", scope_type="country", questions=[])
        self.assertEqual([p["source_ids"] for p in result["phases"]], [["A"], ["R"], ["G"]])
        self.assertNotIn("B", sum((p["source_ids"] for p in result["phases"]), []))

    def test_category_generic_multi_category_and_explicit_associations(self):
        cat = {"G": source("G"), "C": source("C", categories=["CAT1", "CAT2"]), "E": source("E", categories=["CAT2"])}
        links = [{"location": "template.lookup_sources", "lookup_source": "E"}]
        questions = [{"name": "q1", "assessment_category": "CAT1"}, {"name": "q2", "assessment_category": "CAT2"}]
        result = resolve_sources(cat, self.territories, run_territory="CountryA", scope_type="country", questions=questions, explicit_links=links)
        self.assertEqual(result["generic_source_ids"], ["G"])
        self.assertEqual(result["question_sources"], {"q1": ["E", "C"], "q2": ["E", "C"]})

    def test_shared_parent_descendant_source_appears_in_earliest_phase_only(self):
        shared = source("SHARED", ["Region", "CountryA"])
        result = resolve_sources({"SHARED": shared}, self.territories, run_territory="Region", scope_type="region", questions=[])
        self.assertEqual([p["source_ids"] for p in result["phases"]], [[], ["SHARED"], [], []])
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

    def test_preparation_composes_live_context_catalogue_territory_and_plan(self):
        template = {"name": "T", "document_type": "CRM Organization", "master_prompt": "P",
                    "result_contract": "{}", "assessment_questions": [{"name": "q", "assessment_category": "CAT"}],
                    "lookup_sources": [{"name": "template-link-row", "idx": 1, "lookup_source": "EXPLICIT"}]}
        master = source("EXPLICIT", ["Region"])
        context = type("Context", (), {"assessment_template": template,
            "assessment_questions": template["assessment_questions"], "organization": None,
            "lookup_source_links": [{"location": "template.lookup_sources", "question_row_name": None,
                "child_row_name": "template-link-row", "child_row_idx": 1, "lookup_source": "EXPLICIT",
                "child_row": template["lookup_sources"][0]}], "lookup_source_records": {"EXPLICIT": master}})()
        repo = Mock()
        repo.prepare_create_read_context.return_value = context
        repo.get_source_catalogue.return_value = {"EXPLICIT": master, "GEN": source("GEN")}
        repo.list_documents.return_value = [
            {"name": "Region", "parent_crm_territory": None, "lft": 1, "rgt": 4},
            {"name": "Country", "parent_crm_territory": "Region", "lft": 2, "rgt": 3},
        ]
        prepared = ResearchPackagePreparer(repo).prepare_create("T", {}, run_territory="Region")
        plan = json.loads(prepared["files"]["research_plan.json"])
        self.assertEqual(plan["phases"][1]["source_ids"], ["EXPLICIT"])
        self.assertEqual(plan["template_explicit_source_ids"], ["EXPLICIT"])
        self.assertEqual(plan["question_categories"], {"q": "CAT"})

    def test_existing_package_directory_is_not_overwritten(self):
        config = {"assessment_template": {"master_prompt": "p", "result_contract": "{}"}}
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "existing"
            target.mkdir()
            (target / "keep.txt").write_text("keep")
            with self.assertRaises(FileExistsError):
                PackageAssembler().assemble(config, {}, output_dir=target)
            self.assertEqual((target / "keep.txt").read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
