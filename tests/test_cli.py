import unittest

from abm.cli import parse_command


class RunCommandTests(unittest.TestCase):
    def test_accepts_create(self):
        command = parse_command(["run", "--assessment-operation", "CREATE"])
        self.assertEqual(command.assessment_operation, "CREATE")

    def test_accepts_update(self):
        command = parse_command(["run", "--assessment-operation", "UPDATE"])
        self.assertEqual(command.assessment_operation, "UPDATE")

    def test_operation_is_case_insensitive(self):
        command = parse_command(["run", "--assessment-operation", "create"])
        self.assertEqual(command.assessment_operation, "CREATE")

    def test_rejects_missing_operation(self):
        with self.assertRaises(SystemExit) as result:
            parse_command(["run"])
        self.assertEqual(result.exception.code, 2)

    def test_rejects_invalid_operation(self):
        with self.assertRaises(SystemExit) as result:
            parse_command(["run", "--assessment-operation", "REASSESS"])
        self.assertEqual(result.exception.code, 2)

    def test_operation_and_stage_are_independent(self):
        command = parse_command([
            "run", "--assessment-operation", "UPDATE", "--research-stage", "DISCOVERY"
        ])
        self.assertEqual(command.assessment_operation, "UPDATE")
        self.assertEqual(command.research_stage, "DISCOVERY")

    def test_rejects_unknown_stage(self):
        with self.assertRaises(SystemExit) as result:
            parse_command(["run", "--assessment-operation", "CREATE", "--research-stage", "OTHER"])
        self.assertEqual(result.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
