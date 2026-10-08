import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

import ai_actions
import main
from generation_models import EntryItem, EntryPackage


@patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.files = {
            "lp": ("lp.json", b'[{"number": "01"}]', "application/json"),
            "entry_docs": ("entry_docs.json", b'{"packing_list": {"line_items": []}}', "application/json"),
        }
        self.item = {name: "" for name in EntryItem.model_fields}
        self.item["packages"] = [{name: "" for name in EntryPackage.model_fields}]
        self.patcher = patch("ai_actions.OpenAI")
        self.factory = self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.api = self.factory.return_value.__enter__.return_value
        self.respond({"items": [self.item]})

    def respond(self, output, status="completed"):
        self.api.responses.create.return_value = SimpleNamespace(
            status=status, output_text=json.dumps(output)
        )

    def test_uploads_prompt_schema_and_array_response(self):
        response = self.client.post("/generate-entry-items", files=self.files)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), [self.item])
        request = self.api.responses.create.call_args.kwargs
        self.assertTrue(request["instructions"].startswith(ai_actions.GENERATION_PROMPT_PATH.read_text(encoding="utf-8")))
        for block, (filename, data, _) in zip(request["input"][0]["content"], self.files.values()):
            self.assertEqual(block["text"], filename + ":\n" + data.decode())
        self.assertTrue(request["text"]["format"]["strict"])
        self.assertEqual(request["text"]["format"]["schema"]["type"], "object")
        self.assertFalse(request["store"])

    def test_invalid_inputs_do_not_call_api(self):
        for field, data in [("lp", b"bad"), ("entry_docs", b"bad"), ("lp", b"{}"), ("entry_docs", b"[]"), ("lp", b"\xff")]:
            with self.subTest(field=field, data=data):
                files = dict(self.files)
                files[field] = (field + ".json", data, "application/json")
                self.assertEqual(self.client.post("/generate-entry-items", files=files).status_code, 400)
        self.factory.assert_not_called()

    def test_required_files(self):
        for field in self.files:
            self.assertEqual(self.client.post("/generate-entry-items", files={field: self.files[field]}).status_code, 422)
        self.factory.assert_not_called()

    @patch.object(ai_actions, "MAX_DOCUMENT_BYTES", 10)
    def test_upload_limit(self):
        self.assertEqual(self.client.post("/generate-entry-items", files=self.files).status_code, 413)
        self.factory.assert_not_called()

    def test_rejects_invalid_model_outputs(self):
        for output in ({"items": [{}]}, {"items": [{**self.item, "number": 1}]}, {"items": [{**self.item, "unexpected": "x"}]}, {"items": [{**self.item, "packages": [{"code": "x"}]}]}, [self.item], "not json"):
            with self.subTest(output=output):
                self.respond(output)
                self.assertEqual(self.client.post("/generate-entry-items", files=self.files).status_code, 502)

    def test_incomplete_output(self):
        self.respond({"items": [self.item]}, status="incomplete")
        self.assertEqual(self.client.post("/generate-entry-items", files=self.files).status_code, 502)

    @patch.dict(os.environ, {"OPENAI_API_KEY": ""})
    def test_missing_key(self):
        self.assertEqual(self.client.post("/generate-entry-items", files=self.files).status_code, 503)
        self.factory.assert_not_called()
