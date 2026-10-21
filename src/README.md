# Shipment document summaries

Run commands from the project root (the folder containing `pyproject.toml`).
Install dependencies with `uv sync`. Set `OPENAI_API_KEY` in your environment,
then start the server with `uv run fastapi dev`. Alternatively, copy
your environment settings to `src/.env`, supply your key, and run
`uv run uvicorn src.main:app --reload --env-file src/.env`.
`OPENAI_MODEL` optionally overrides the default `gpt-4.1`; use a model that
supports PDF inputs through the Responses API.

Open http://127.0.0.1:8000/docs to upload documents interactively.

- `POST /parse-documents` saves PDFs without calling OpenAI.
- `POST /executive-summary` saves PDFs, sends all supplied PDFs to OpenAI together,
  and returns `executive_summary` (Markdown) plus the saved `documents` paths.
- `POST /extract-entry-documents` saves PDFs and returns the structured
  `commercial_invoice`, `packing_list`, and `certificate_of_origin` objects directly.
  It uses `prompt_revamp.md` and the project's `UN-CEFACT-Rec21.xlsx` and omits the
  extraction report.

All three endpoints require `commercial_invoice`, `packing_list`, and
`certificate_of_origin`. Optional PDF fields are `bill_of_lading`, `insurance`,
and `import_declaration_form`. The combined PDF size must be under 50 MB.
Only files in the current request are summarized; `entry_docs.json` is sample
data, not evidence for the shipment. PDFs are retained locally in `attachments/`,
including if summary generation fails. API usage is billed to your OpenAI account.

```sh
curl http://127.0.0.1:8000/executive-summary \
  -F 'commercial_invoice=@invoice.pdf;type=application/pdf' \
  -F 'packing_list=@packing.pdf;type=application/pdf' \
  -F 'certificate_of_origin=@origin.pdf;type=application/pdf' \
  -F 'bill_of_lading=@bill.pdf;type=application/pdf'
```

The summary covers shipment details, financials, document discrepancies, missing
information, and next actions, with requested source references. Review generated
facts and references against the originals. Large or dense PDFs may exceed the
model's context limit even within the file size limit; such requests return an
error rather than a partial summary. Missing API configuration returns 503;
upstream failures return 502/503 and timeouts return 504.

Integration follows the official [OpenAI file inputs guide](https://developers.openai.com/api/docs/guides/file-inputs).

Run offline tests with `uv run python -m unittest discover -s tests`.

For structured extraction, call `extract_entry_documents` from Python:

```python
from pathlib import Path
from src.ai_actions import extract_entry_documents

documents = {path.stem: path for path in Path("attachments").glob("*.pdf")}
result = extract_entry_documents(documents)
```

Use one shipment per call. The function reads `prompt_revamp.md` on each call,
overrides its report/delivery instructions, and returns a validated dictionary
containing only `commercial_invoice`, `packing_list`, and `certificate_of_origin`.
It does not generate an extraction report or write files. All scalar values are
strings; missing values are blank strings or empty arrays. The project's
`UN-CEFACT-Rec21.xlsx` is automatically included for package-code lookups, resolved
relative to `ai_actions.py` regardless of the working directory. Pass
`package_reference=Path("another-workbook.xlsx")` to override it.
Output follows the [Structured Outputs API](https://developers.openai.com/api/docs/guides/structured-outputs).
