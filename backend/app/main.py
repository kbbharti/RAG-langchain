import os
from uuid import UUID, uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.database import check_database, history, save_exchange
from app.ingestion import pdf_chunks
from app.rag import index_documents, missing_databricks_config, answer_question

load_dotenv()
app = FastAPI(title="PDF RAG API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    session_id: UUID | None = None


class ChatResponse(BaseModel):
    session_id: UUID
    answer: str
    citations: list[dict]


@app.get("/health")
def health() -> dict:
    database_configured = bool(os.getenv("DATABASE_URL"))
    database_ok = check_database() if database_configured else False
    missing = missing_databricks_config()
    return {
        "status": "ok" if database_ok and not missing else "degraded",
        "database": "ok" if database_ok else "unavailable",
        "databricks_configured": not missing,
        "missing_databricks_config": missing,
    }


@app.post("/ingest")
def ingest(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload a PDF file.")
    try:
        documents = pdf_chunks(file.file.read(), file.filename)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read PDF: {exc}") from exc

    try:
        count = index_documents(documents)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Databricks indexing failed; check endpoint and index configuration."
        ) from exc
    return {"filename": file.filename, "chunks_indexed": count}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    session_id = request.session_id or uuid4()
    try:
        prior_history = history(session_id)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="PostgreSQL is unavailable or DATABASE_URL is missing.",
        ) from exc

    try:
        answer, citations = answer_question(request.question, prior_history)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Databricks retrieval or generation failed; check service configuration.",
        ) from exc

    try:
        save_exchange(session_id, request.question, answer, citations)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="Could not save conversation to PostgreSQL."
        ) from exc
    return ChatResponse(session_id=session_id, answer=answer, citations=citations)
