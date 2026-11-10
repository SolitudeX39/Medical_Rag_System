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
from components.clinic import (
    DEPARTMENTS,
    PATIENT_PROMPTS,
    TRIAGE_PROMPTS,
    authenticate,
    get_patient,
    patient_chat,
    triage_chat,
)
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

app = FastAPI(title="Medical Clinic AI")

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
    username: str = ""


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


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
    return {
        "prompts": SUGGESTED_PROMPTS,
        "graph_prompts": GRAPH_BUILD_PROMPTS,
        "triage_prompts": TRIAGE_PROMPTS,
        "patient_prompts": PATIENT_PROMPTS,
    }


@app.post("/auth/login")
def auth_login(body: LoginRequest):
    session = authenticate(body.username, body.password)
    if not session:
        raise HTTPException(status_code=401, detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    return session


@app.get("/clinic/departments")
def clinic_departments():
    return {"departments": DEPARTMENTS}


@app.get("/patients/{username}")
def patient_profile(username: str):
    patient = get_patient(username)
    if not patient:
        raise HTTPException(status_code=404, detail="ไม่พบคนไข้")
    return patient


@app.post("/triage")
def triage(body: ChatRequest):
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message required")
    try:
        result = triage_chat(message, history=[item.model_dump() for item in body.history])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@app.post("/patient/chat")
def patient_advice(body: ChatRequest):
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message required")
    try:
        return patient_chat(
            body.username,
            message,
            history=[item.model_dump() for item in body.history],
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".csv"}:
        raise HTTPException(status_code=400, detail="กรุณาอัปโหลดไฟล์ PDF หรือ CSV")

    upload_dir = ROOT / "uploads"
    upload_dir.mkdir(exist_ok=True)

    is_medical_csv = False
    ner_summary = None
    result = {}

    with tempfile.TemporaryDirectory(dir=upload_dir) as tmp_dir:
        saved_path = Path(tmp_dir) / filename
        saved_path.write_bytes(await file.read())

        if suffix == ".csv":
            try:
                import pandas as pd
                df_peek = pd.read_csv(saved_path, nrows=5)
                cols = [str(c).lower().strip() for c in df_peek.columns]
                if any(c in cols for c in ["disease", "common_symptom", "treatment"]):
                    is_medical_csv = True
            except Exception as e:
                print(f"Note: Error inspecting CSV columns: {e}")

        # If medical disease/symptom/treatment CSV, execute the Biomedical NER + UMLS RDF Pipeline!
        if is_medical_csv:
            try:
                from .ner_rdflib_pipeline import process_csv_to_rdf
                from upload_ttl_to_aura import (
                    AURA_PASSWORD,
                    AURA_URI,
                    AURA_USERNAME,
                    upload_ttl_to_aura,
                )

                ttl_output = upload_dir / f"{Path(filename).stem}_graph.ttl"
                print(f"Running Biomedical NER + UMLS CUI pipeline on {filename}...")
                process_csv_to_rdf(str(saved_path), output_path=str(ttl_output))

                print(f"Syncing generated triples from {ttl_output} to Neo4j Aura...")
                upload_ttl_to_aura(str(ttl_output), AURA_URI, AURA_USERNAME, AURA_PASSWORD)
                ner_summary = "แปลงเอนทิตีอาการและยาด้วย UMLS CUI และอัปเดต Neo4j Knowledge Graph เรียบร้อยแล้ว"
            except Exception as ner_exc:
                print(f"Warning: NER RDF pipeline run failed: {ner_exc}")
                ner_summary = f"NER pipeline notice: {ner_exc}"

        # Also store into PostgreSQL vector database for hybrid text search if available
        try:
            result = insert_into_database(saved_path)
        except Exception as exc:
            if is_medical_csv:
                result = {"filename": filename, "parent_chunks": 1, "note": "Indexed to Neo4j Knowledge Graph"}
            else:
                raise HTTPException(status_code=500, detail=str(exc)) from exc

    overview = graph_overview(limit=100)
    return {
        "status": "indexed",
        "filename": filename,
        "is_medical_dataset": is_medical_csv,
        "ner_summary": ner_summary,
        "graph": overview,
        **result,
    }


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
