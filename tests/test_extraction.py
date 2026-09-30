import base64
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

import ai_actions


@patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
class ExtractionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.pdf = Path(temporary.name) / "invoice.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\nexample")
        self.documents = {"commercial_invoice": self.pdf}
        self.prompt = ai_actions.EXTRACTION_PROMPT_PATH.read_text(encoding="utf-8")
        self.output = json.loads(re.search(r"```json\s*(.*?)```", self.prompt, re.S)[1])
        self.patcher = patch("ai_actions.OpenAI")
        self.factory = self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.api = self.factory.return_value.__enter__.return_value

    def respond(self, output, status="completed"):
        self.api.responses.create.return_value = SimpleNamespace(status=status, output_text=output)

    def test_prompt_structure_and_no_report_override(self):
        self.respond(json.dumps(self.output))
        self.assertEqual(ai_actions.extract_entry_documents(self.documents), self.output)
        request = self.api.responses.create.call_args.kwargs
        self.assertTrue(request["instructions"].startswith(self.prompt))
        self.assertIn("Do not generate an extraction report", request["instructions"])
        self.assertTrue(request["text"]["format"]["strict"])
        self.assertEqual(set(request["text"]["format"]["schema"]["properties"]), set(self.output))
        content = request["input"][0]["content"]
        self.assertEqual(len(content), 3)
        self.assertEqual(content[-1]["filename"], "UN-CEFACT-Rec21.xlsx")
        self.assertEqual(
            base64.b64decode(content[-1]["file_data"].split(",", 1)[1]),
            ai_actions.PACKAGE_REFERENCE_PATH.read_bytes(),
        )
        self.assertFalse(request["store"])

    def test_schema_requires_every_property_and_forbids_null(self):
        schema = ai_actions.ExtractedEntryDocuments.model_json_schema()

        def check(node):
            if isinstance(node, dict):
                self.assertNotEqual(node.get("type"), "null")
                if node.get("type") == "object":
                    self.assertEqual(set(node["required"]), set(node["properties"]))
                    self.assertIs(node["additionalProperties"], False)
                for value in node.values():
                    check(value)
            elif isinstance(node, list):
                for value in node:
                    check(value)

        check(schema)

    def test_idf_values_preserve_leading_zeros_and_quantity_units(self):
        idf = self.output["import_declaration_form"]
        idf["importer"]["county_code"] = "01"
        idf["line_items"] = [{
            "number": "01", "name": "Goods", "qty": "2.50",
            "qty_unit": "KGM", "origin": "KE", "hs_code": "01012100",
            "net_mass": "2.50", "fob_value": "100.00",
        }]
        self.respond(json.dumps(self.output))
        self.assertEqual(ai_actions.extract_entry_documents(self.documents), self.output)

    def test_report_extra_keys_and_non_string_values_are_rejected(self):
        for invalid in (
            {**self.output, "extraction_report": {}},
            {**self.output, "commercial_invoice": {**self.output["commercial_invoice"], "fob_amount": 123}},
            {},
        ):
            with self.subTest(invalid=invalid):
                self.respond(json.dumps(invalid))
                with self.assertRaises(HTTPException) as raised:
                    ai_actions.extract_entry_documents(self.documents)
                self.assertEqual(raised.exception.status_code, 502)

    def test_empty_arrays_are_accepted(self):
        self.output["commercial_invoice"]["line_items"] = []
        self.output["packing_list"]["line_items"] = []
        self.output["import_declaration_form"]["line_items"] = []
        self.respond(json.dumps(self.output))
        self.assertEqual(ai_actions.extract_entry_documents(self.documents), self.output)

    def test_invalid_empty_or_incomplete_response(self):
        for text, status in [("not json", "completed"), ("", "completed"), (json.dumps(self.output), "incomplete")]:
            with self.subTest(text=text, status=status):
                self.respond(text, status)
                with self.assertRaises(HTTPException) as raised:
                    ai_actions.extract_entry_documents(self.documents)
                self.assertEqual(raised.exception.status_code, 502)

    def test_missing_documents(self):
        with self.assertRaises(HTTPException) as raised:
            ai_actions.extract_entry_documents({})
        self.assertEqual(raised.exception.status_code, 400)
        self.factory.assert_not_called()

    def test_invalid_pdf(self):
        self.pdf.write_bytes(b"not PDF")
        with self.assertRaises(HTTPException) as raised:
            ai_actions.extract_entry_documents(self.documents)
        self.assertEqual(raised.exception.status_code, 415)
        self.factory.assert_not_called()

    @patch.dict(os.environ, {"OPENAI_API_KEY": ""})
    def test_missing_key(self):
        with self.assertRaises(HTTPException) as raised:
            ai_actions.extract_entry_documents(self.documents)
        self.assertEqual(raised.exception.status_code, 503)
        self.factory.assert_not_called()
