import contextlib
import io
import unittest

from abm.cli import main


class CLITests(unittest.TestCase):
    def test_top_level_help_lists_unified_commands(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            import sys
            old_argv = sys.argv
            sys.argv = ["abm", "--help"]
            try:
                main()
            finally:
                sys.argv = old_argv
        self.assertEqual(raised.exception.code, 0)
        for command in ("discover", "research", "assess", "run", "status", "report"):
            self.assertIn(command, output.getvalue())


if __name__ == "__main__":
    unittest.main()
