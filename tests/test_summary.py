import base64
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from src import main
from src import ai_actions


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.directory_patch = patch.object(main, "ATTACHMENTS_DIR", self.directory)
        self.directory_patch.start()
        self.addCleanup(self.directory_patch.stop)
        self.client = TestClient(main.app)

    def files(self, optional=False):
        names = ["commercial_invoice", "packing_list", "certificate_of_origin"]
        if optional:
            names += ["bill_of_lading", "insurance", "import_declaration_form"]
        return {name: (f"{name}.pdf", b"%PDF-1.4\n" + name.encode(), "application/pdf") for name in names}

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("src.ai_actions.OpenAI")
    def test_extraction_endpoint(self, factory):
        prompt = ai_actions.EXTRACTION_PROMPT_PATH.read_text()
        expected = json.loads(re.search(r"```json\s*(.*?)```", prompt, re.S)[1])
        api = factory.return_value.__enter__.return_value
        api.responses.create.return_value = SimpleNamespace(
            status="completed", output_text=json.dumps(expected)
        )
        response = self.client.post("/extract-entry-documents", files=self.files(optional=True))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), expected)
        content = api.responses.create.call_args.kwargs["input"][0]["content"]
        self.assertEqual(len(content), 8)  # Prompt, six PDFs, and the reference workbook.
        self.assertEqual(content[-1]["filename"], "UN-CEFACT-Rec21.xlsx")

    @patch("src.main.extract_entry_documents")
    def test_extraction_endpoint_requires_uploads(self, extract):
        response = self.client.post("/extract-entry-documents")
        self.assertEqual(response.status_code, 422)
        extract.assert_not_called()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("src.ai_actions.OpenAI")
    def test_all_documents_are_sent_and_summary_returned(self, factory):
        api = factory.return_value.__enter__.return_value
        api.responses.create.return_value = SimpleNamespace(status="completed", output_text="Shipment summary")
        files = self.files(optional=True)
        response = self.client.post("/executive-summary", files=files)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["executive_summary"], "Shipment summary")
        request = api.responses.create.call_args.kwargs
        inputs = request["input"][0]["content"][1:]
        self.assertEqual(len(inputs), 6)
        for item in inputs:
            name = Path(item["filename"]).stem
            self.assertEqual(base64.b64decode(item["file_data"].split(",", 1)[1]), files[name][1])
        self.assertFalse(request["store"])
        self.assertEqual(len(list(self.directory.glob("*.pdf"))), 6)

    @patch("src.ai_actions.OpenAI")
    def test_parse_documents_does_not_call_openai(self, factory):
        response = self.client.post("/parse-documents", files=self.files())
        self.assertEqual(response.status_code, 200)
        factory.assert_not_called()

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_key(self):
        response = self.client.post("/executive-summary", files=self.files())
        self.assertEqual(response.status_code, 503)

    def test_invalid_pdf_saves_nothing(self):
        files = self.files()
        files["packing_list"] = ("bad.pdf", b"not a pdf", "application/pdf")
        response = self.client.post("/executive-summary", files=files)
        self.assertEqual(response.status_code, 415)
        self.assertEqual(list(self.directory.iterdir()), [])

    @patch.object(main, "MAX_DOCUMENT_BYTES", 30)
    def test_combined_size_limit(self):
        response = self.client.post("/executive-summary", files=self.files())
        self.assertEqual(response.status_code, 413)
        self.assertEqual(list(self.directory.iterdir()), [])

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("src.ai_actions.OpenAI")
    def test_incomplete_summary_is_not_returned_as_success(self, factory):
        api = factory.return_value.__enter__.return_value
        api.responses.create.return_value = SimpleNamespace(status="incomplete", output_text="Partial")
        response = self.client.post("/executive-summary", files=self.files())
        self.assertEqual(response.status_code, 502)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("src.ai_actions.OpenAI")
    def test_connection_failure(self, factory):
        import httpx

        api = factory.return_value.__enter__.return_value
        api.responses.create.side_effect = ai_actions.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))
        response = self.client.post("/executive-summary", files=self.files())
        self.assertEqual(response.status_code, 502)


if __name__ == "__main__":
    unittest.main()
