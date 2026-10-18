from functools import lru_cache

import anthropic
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile

from .ingest import UnsupportedFileError, extract_text, split_into_chunks
from .llm import LLM, ClaudeRefusalError, ClaudeService
from .schemas import (
    AskRequest,
    AskResponse,
    DocType,
    ExtractRequest,
    IngestResponse,
    JobPosting,
    MatchRequest,
    MatchResult,
    TextDocumentRequest,
)
from .store import PgVectorStore, VectorStore

app = FastAPI(
    title="JobFit AI",
    description="RAG and structured extraction over resumes and job postings.",
    version="0.1.0",
)


@lru_cache
def get_store() -> VectorStore:
    return PgVectorStore()


@lru_cache
def get_llm() -> LLM:
    return ClaudeService()


def _ingest(text: str, source: str, doc_type: DocType, store: VectorStore) -> IngestResponse:
    chunks = split_into_chunks(text, source=source, doc_type=doc_type.value)
    if not chunks:
        raise HTTPException(status_code=422, detail="The document contains no text.")
    added = store.add(chunks)
    return IngestResponse(source=source, doc_type=doc_type, chunks_added=added)


def _call_claude(fn, *args):
    try:
        return fn(*args)
    except ClaudeRefusalError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except anthropic.RateLimitError as exc:
        raise HTTPException(status_code=429, detail="Claude rate limit reached, try again shortly.") from exc
    except anthropic.APIStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Claude API error: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise HTTPException(status_code=503, detail="Could not reach the Claude API.") from exc


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/documents", response_model=IngestResponse)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: DocType = Form(DocType.other),
    store: VectorStore = Depends(get_store),
) -> IngestResponse:
    data = await file.read()
    try:
        text = extract_text(file.filename or "upload", data)
    except UnsupportedFileError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    return _ingest(text, file.filename or "upload", doc_type, store)


@app.post("/documents/text", response_model=IngestResponse)
def add_text_document(req: TextDocumentRequest, store: VectorStore = Depends(get_store)) -> IngestResponse:
    return _ingest(req.text, req.source, req.doc_type, store)


@app.post("/ask", response_model=AskResponse)
def ask(
    req: AskRequest,
    store: VectorStore = Depends(get_store),
    llm: LLM = Depends(get_llm),
) -> AskResponse:
    chunks = store.search(req.question, k=req.k, doc_type=req.doc_type.value if req.doc_type else None)
    if not chunks:
        return AskResponse(answer="No documents have been added yet.", citations=[], sources=[])
    return _call_claude(llm.answer, req.question, chunks)


@app.post("/extract", response_model=JobPosting)
def extract(req: ExtractRequest, llm: LLM = Depends(get_llm)) -> JobPosting:
    return _call_claude(llm.extract_job, req.job_text)


@app.post("/match", response_model=MatchResult)
def match(
    req: MatchRequest,
    store: VectorStore = Depends(get_store),
    llm: LLM = Depends(get_llm),
) -> MatchResult:
    resume_text = req.resume_text
    if not resume_text:
        # RAG step: pull the resume sections most relevant to this job.
        chunks = store.search(req.job_text, k=6, doc_type=DocType.resume.value)
        if not chunks:
            raise HTTPException(status_code=422, detail="Add a resume first, or pass resume_text.")
        resume_text = "\n\n".join(c.text for c in chunks)
    return _call_claude(llm.match, resume_text, req.job_text)
