import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from abm.cli import main
from abm.config import ConfigurationError, load_config
from abm.package.preparation import ResearchPackagePreparer


def write_config(path: Path, template="", region="", output="packages"):
    path.write_text(
        "[defaults]\n"
        f'organization_assessment_template = "{template}"\n'
        f'regional_territory = "{region}"\n'
        f'package_output_dir = "{output}"\n',
        encoding="utf-8",
    )


class ConfigurationTests(unittest.TestCase):
    def test_loads_defaults_and_preserves_empty_selection_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "abm.toml"
            write_config(config_path, output="out")
            config = load_config(config_path)
        self.assertIsNone(config.organization_assessment_template)
        self.assertIsNone(config.regional_territory)
        self.assertEqual(config.package_output_dir, Path("out"))

    def test_missing_configuration_fails_clearly(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ConfigurationError, "Configuration file not found"):
                load_config(Path(tmp) / "missing.toml")

    def test_configuration_rejects_credentials_without_echoing_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "abm.toml"
            config_path.write_text('[defaults]\napi_secret = "NEVER_PRINT_THIS"\n')
            with self.assertRaises(ConfigurationError) as caught:
                load_config(config_path)
        self.assertNotIn("NEVER_PRINT_THIS", str(caught.exception))
        self.assertIn("api_secret", str(caught.exception))


class PrepareCLITests(unittest.TestCase):
    def test_cli_overrides_config_and_executes_regional_preparation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "abm.toml"
            write_config(config_path, "configured-template", "Configured Region", "configured-out")
            def src(name, territories=()):
                return {"name": name, "source_name": name, "url": f"https://{name.lower()}.example",
                        "disabled": 0,
                        "applicable_territories": [{"name": f"{name}-t{i}", "territory": terr}
                            for i, terr in enumerate(territories)],
                        "applicable_assessment_categories": []}
            template = {"name": "CLI Template", "document_type": "CRM Organization",
                        "master_prompt": "prompt bytes", "result_contract": "contract bytes",
                        "assessment_questions": [{"name": "q1", "assessment_category": "CAT"}],
                        "lookup_sources": []}
            context = SimpleNamespace(assessment_template=template,
                assessment_questions=template["assessment_questions"], organization=None,
                lookup_source_links=[], lookup_source_records={})
            repo = Mock()
            repo.prepare_create_read_context.return_value = context
            repo.get_source_catalogue.return_value = {
                "GLOBAL": src("GLOBAL"), "REGIONAL": src("REGIONAL", ["Europe"]),
                "OUTSIDE": src("OUTSIDE", ["Asia"]),
            }
            repo.list_documents.return_value = [
                {"name": "Europe", "parent_crm_territory": None, "lft": 1, "rgt": 4, "is_group": 1},
                {"name": "France", "parent_crm_territory": "Europe", "lft": 2, "rgt": 3, "is_group": 0},
                {"name": "Asia", "parent_crm_territory": None, "lft": 5, "rgt": 8, "is_group": 1},
                {"name": "Japan", "parent_crm_territory": "Asia", "lft": 6, "rgt": 7, "is_group": 0},
            ]
            output = []
            errors = []
            code = main([
                "prepare", "--assessment-operation", "CREATE", "--research-stage", "DISCOVERY",
                "--template", "CLI Template", "--region", "Europe", "--output-dir", str(root / "cli-out"),
                "--config", str(config_path),
            ], preparer_factory=lambda: ResearchPackagePreparer(repo), output=output.append, error_output=errors.append)
            self.assertEqual(code, 0)
            self.assertEqual(errors, [])
            self.assertIn("retrieved=3 selected=2 excluded=1", " ".join(output))
            self.assertIn("  regional (Europe): 1 source", output)
            package_path = Path(output[0].removeprefix("Package: "))
            self.assertEqual(package_path.parent, root / "cli-out")
            self.assertTrue((package_path / "manifest.json").is_file())
            import json
            catalogue = json.loads((package_path / "source_catalogue.json").read_text())
            self.assertEqual(set(catalogue), {"GLOBAL", "REGIONAL", "OUTSIDE"})

    def test_config_defaults_are_used_when_cli_values_are_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "abm.toml"
            write_config(config_path, "T-CRM", "Europe", str(root / "packages"))
            preparer = Mock()
            preparer.prepare_create.return_value = {"preparation_summary": {
                "catalogue_retrieved": 0, "applicable_selected": 0, "excluded": 0,
                "phase_counts": [],
            }}
            code = main([
                "prepare", "--assessment-operation", "CREATE", "--research-stage", "FULL_ASSESSMENT",
                "--config", str(config_path),
            ], preparer_factory=lambda: preparer, output=lambda _: None, error_output=lambda _: None)
        self.assertEqual(code, 0)
        self.assertEqual(preparer.prepare_create.call_args.args[0], "T-CRM")
        self.assertEqual(preparer.prepare_create.call_args.kwargs["run_territory"], "Europe")

    def test_missing_template_or_region_fails_before_crm_preparation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "abm.toml"
            write_config(config_path, "", "", "packages")
            preparer = Mock()
            errors = []
            code = main([
                "prepare", "--assessment-operation", "CREATE", "--research-stage", "DISCOVERY",
                "--template", "T", "--config", str(config_path),
            ], preparer_factory=lambda: preparer, output=lambda _: None, error_output=errors.append)
        self.assertEqual(code, 2)
        self.assertIn("Missing required region", errors[0])
        preparer.prepare_create.assert_not_called()

    def test_update_preparation_is_explicitly_unsupported(self):
        preparer = Mock()
        errors = []
        code = main([
            "prepare", "--assessment-operation", "UPDATE", "--research-stage", "FULL_ASSESSMENT",
            "--template", "T", "--region", "Europe", "--output-dir", "out",
        ], preparer_factory=lambda: preparer, output=lambda _: None, error_output=errors.append)
        self.assertEqual(code, 2)
        self.assertIn("UPDATE package preparation is unsupported", errors[0])
        preparer.prepare_create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
