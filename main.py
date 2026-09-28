from pathlib import Path
from typing import Annotated
from uuid import uuid4
from dotenv import load_dotenv

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile

from ai_actions import MAX_DOCUMENT_BYTES, create_executive_summary, extract_entry_documents
from extraction_models import ExtractedEntryDocuments

load_dotenv()
app = FastAPI()
ATTACHMENTS_DIR = Path(__file__).resolve().parent / "attachments"


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/parse-documents")
def parse_documents(
    commercial_invoice: Annotated[UploadFile, File(description="Commercial invoice PDF")],
    packing_list: Annotated[UploadFile, File(description="Packing list PDF")],
    certificate_of_origin: Annotated[
        UploadFile, File(description="Certificate of origin PDF")
    ],
    bill_of_lading: Annotated[UploadFile | None, File()] = None,
    insurance: Annotated[UploadFile | None, File()] = None,
    import_declaration_form: Annotated[UploadFile | None, File()] = None,
):
    documents:dict[str, UploadFile] = {
        "commercial_invoice": commercial_invoice,
        "packing_list": packing_list,
        "certificate_of_origin": certificate_of_origin,
        "bill_of_lading": bill_of_lading,
        "insurance": insurance,
        "import_declaration_form": import_declaration_form,
    }
    documents = {name: document for name, document in documents.items() if document is not None}
    contents = {}
    total_bytes = 0
    for name, document in documents.items():
        if document.content_type != "application/pdf":
            raise HTTPException(
                status_code=415,
                detail=f"{name} must be uploaded as application/pdf.",
            )
        data = document.file.read(MAX_DOCUMENT_BYTES - total_bytes + 1)
        total_bytes += len(data)
        if total_bytes >= MAX_DOCUMENT_BYTES:
            raise HTTPException(status_code=413, detail="Combined PDFs must be under 50 MB.")
        if not data.startswith(b"%PDF-"):
            raise HTTPException(status_code=415, detail=f"{name} is not a PDF file.")
        contents[name] = data

    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    # upload_id = uuid4().hex
    saved_documents:dict[str, str] = {}
    for name, data in contents.items():
        # filename = f"{name}_{upload_id}.pdf"
        filename = f"{name}.pdf"
        (ATTACHMENTS_DIR / filename).write_bytes(data)
        saved_documents[name] = f"attachments/{filename}"

    return {
        "message": "Documents saved successfully",
        "documents": saved_documents,
    }


@app.post("/executive-summary")
def executive_summary(saved: Annotated[dict, Depends(parse_documents)]):
    """Save the uploaded PDFs and summarize the complete document set together."""
    paths:dict[str, Path] = {
        name: ATTACHMENTS_DIR / Path(path).name
        for name, path in saved["documents"].items()
    }
    summary = create_executive_summary(paths)
    return {"executive_summary": summary, "documents": saved["documents"]}


@app.post("/extract-entry-documents", response_model=ExtractedEntryDocuments)
def extract_documents(saved: Annotated[dict, Depends(parse_documents)]):
    """Save uploaded PDFs and return structured shipment data without an extraction report."""
    paths:dict[str, Path] = {
        name: ATTACHMENTS_DIR / Path(path).name
        for name, path in saved["documents"].items()
    }
    return extract_entry_documents(paths)
