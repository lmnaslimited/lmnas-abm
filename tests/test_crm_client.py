import json
import subprocess
import unittest
from unittest.mock import Mock

from abm.crm.client import FrappeAPIClient, FrappeAPIError


def completed(stdout, returncode=0, stderr=""):
    return subprocess.CompletedProcess(args=["fr", "api"], returncode=returncode, stdout=stdout, stderr=stderr)


class FrappeAPIClientTests(unittest.TestCase):
    def test_get_document_uses_encoded_document_endpoint(self):
        runner = Mock(return_value=completed('{"name":"BEZ Transformátory"}'))
        client = FrappeAPIClient(runner=runner)

        result = client.get_document("CRM Organization", "BEZ Transformátory")

        self.assertEqual(result["name"], "BEZ Transformátory")
        command = runner.call_args.args[0]
        self.assertEqual(command, [
            "fr", "api", "document/CRM%20Organization/BEZ%20Transform%C3%A1tory"
        ])

    def test_get_serializes_typed_api_parameters(self):
        runner = Mock(return_value=completed('[{"name":"one"}]'))
        client = FrappeAPIClient(runner=runner)

        client.get("document/Assessment%20Category", {
            "fields": ["name"], "filters": [["disabled", "=", 0]], "limit": 10
        })

        command = runner.call_args.args[0]
        self.assertEqual(command, [
            "fr", "api",
            "-F", 'fields:=["name"]',
            "-F", 'filters:=[["disabled","=",0]]',
            "-F", "limit=10",
            "document/Assessment%20Category",
        ])

    def test_list_documents_paginates_using_limit_and_start(self):
        runner = Mock(side_effect=[
            completed('[{"name":"A"},{"name":"B"}]'),
            completed('[{"name":"C"}]'),
        ])
        client = FrappeAPIClient(runner=runner)

        rows = client.list_documents("Assessment Category", page_size=2)

        self.assertEqual([row["name"] for row in rows], ["A", "B", "C"])
        first = runner.call_args_list[0].args[0]
        second = runner.call_args_list[1].args[0]
        self.assertIn("limit=2", first)
        self.assertIn("start=0", first)
        self.assertIn("start=2", second)

    def test_nonzero_exit_does_not_expose_cli_output_or_secret(self):
        runner = Mock(return_value=completed("", returncode=1, stderr="API secret: dont-print"))
        client = FrappeAPIClient(runner=runner)

        with self.assertRaises(FrappeAPIError) as result:
            client.get("document/CRM%20Assessment")

        self.assertNotIn("dont-print", str(result.exception))
        self.assertIn("exit 1", str(result.exception))

    def test_invalid_json_is_rejected(self):
        client = FrappeAPIClient(runner=Mock(return_value=completed("not-json")))
        with self.assertRaisesRegex(FrappeAPIError, "invalid JSON"):
            client.get("document/CRM%20Organization")

    def test_non_object_document_response_is_rejected(self):
        client = FrappeAPIClient(runner=Mock(return_value=completed("[]")))
        with self.assertRaisesRegex(FrappeAPIError, "not a JSON object"):
            client.get_document("CRM Organization", "name")


if __name__ == "__main__":
    unittest.main()
