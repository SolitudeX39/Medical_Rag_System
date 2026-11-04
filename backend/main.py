import os
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from components.env import load_project_env

load_project_env()

from components.chat_prompt import GRAPH_BUILD_PROMPTS, SUGGESTED_PROMPTS
from components.graph_build import build_graph_from_prompt
from components.database import (
    delete_document,
    get_document,
    insert_into_database,
    list_documents,
    query_database,
    seed_mock_pdf_data,
)
from components.graph import graph_overview, related_terms, replace_graph
from components.medical_graph import MEDICAL_GRAPH_NODES, MEDICAL_GRAPH_RELATIONSHIPS
from components.mock_pdf_data import MOCK_PDF_NAME

app = FastAPI(title="Medical RAG AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"),
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[ChatMessage] = []


@app.get("/health")
def health():
    overview = graph_overview()
    return {"ok": True, "neo4j": not overview.get("skipped"), "graph_nodes": len(overview.get("nodes") or [])}


@app.get("/documents")
def documents():
    try:
        return {"documents": list_documents()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/prompts")
def prompts():
    return {"prompts": SUGGESTED_PROMPTS, "graph_prompts": GRAPH_BUILD_PROMPTS}


@app.get("/documents/{document_id}")
def document_detail(document_id: str):
    try:
        detail = get_document(document_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not detail:
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")
    return detail


@app.delete("/documents/{document_id}")
def document_delete(document_id: str):
    try:
        deleted = delete_document(document_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="ไม่พบเอกสาร")
    return {"status": "deleted", **deleted}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    filename = Path(file.filename or "").name
    if Path(filename).suffix.lower() not in {".pdf", ".csv"}:
        raise HTTPException(status_code=400, detail="กรุณาอัปโหลดไฟล์ PDF หรือ CSV")

    upload_dir = ROOT / "uploads"
    upload_dir.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(dir=upload_dir) as tmp_dir:
        saved_path = Path(tmp_dir) / filename
        saved_path.write_bytes(await file.read())
        try:
            result = insert_into_database(saved_path)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"status": "indexed", **result}


@app.post("/seed-mock")
def seed_mock():
    try:
        return {"status": "indexed", **seed_mock_pdf_data()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/graph")
def graph():
    return graph_overview()


@app.get("/graph/search")
def graph_search(q: str = ""):
    return {"facts": related_terms(q)}


@app.post("/graph/seed")
def graph_seed():
    try:
        return replace_graph(MEDICAL_GRAPH_NODES, MEDICAL_GRAPH_RELATIONSHIPS, MOCK_PDF_NAME)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/graph/build")
def graph_build(body: ChatRequest):
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message required")
    try:
        return build_graph_from_prompt(
            message,
            history=[item.model_dump() for item in body.history],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/chat")
def chat(body: ChatRequest):
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message required")

    history = [item.model_dump() for item in body.history]
    try:
        return query_database(message, history=history)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
