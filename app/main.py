import json
import queue
import threading
from functools import lru_cache

import anthropic
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .config import settings
from .ingest import UnsupportedFileError, extract_text, split_into_chunks
from .jobfetch import JobFetchError, JobsDBFetcher, UnsupportedJobUrl
from .jsearch import JSearchClient
from .smartsearch import run_search
from .webfetch import PoliteFetcher
from .limits import DailyLimiter, LimitExceeded, visitor_id
from .llm import LLM, ClaudeRefusalError, ClaudeService
from .observability import RequestContextMiddleware, log, request_id_var, setup_logging
from .schemas import (
    AnalyzeRequest,
    AskRequest,
    AskResponse,
    CoverLetterRequest,
    CoverLetterResponse,
    DocType,
    ExtractRequest,
    FitReport,
    IngestResponse,
    JobFetchRequest,
    JobFetchResponse,
    JobPosting,
    JobSearchRequest,
    MatchRequest,
    MatchResult,
    ResumeParseResponse,
    TextDocumentRequest,
    UsageResponse,
)
from .store import PgVectorStore, VectorStore

app = FastAPI(
    title="JobFit AI",
    description=(
        "Paste a job posting and see how well it fits your resume: fit score, key facts, "
        "matching and missing skills, red flags, and a tailored cover letter."
    ),
    version="1.0.0",
)

setup_logging()
app.add_middleware(RequestContextMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@lru_cache
def get_store() -> VectorStore:
    return PgVectorStore()


@lru_cache
def get_llm() -> LLM:
    return ClaudeService()


@lru_cache
def get_limiter() -> DailyLimiter:
    return DailyLimiter(per_visitor=settings.daily_limit_per_visitor, total=settings.daily_limit_total)


@lru_cache
def get_fetch_limiter() -> DailyLimiter:
    return DailyLimiter(per_visitor=settings.daily_fetch_limit_per_visitor, total=0)


@lru_cache
def get_job_fetcher() -> JobsDBFetcher:
    return JobsDBFetcher()


def _consume(limiter: DailyLimiter, request: Request) -> None:
    try:
        limiter.consume(visitor_id(request))
    except LimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


def use_quota(request: Request, limiter: DailyLimiter = Depends(get_limiter)) -> None:
    """Dependency for every endpoint that calls Claude."""
    _consume(limiter, request)


@lru_cache
def get_search_limiter() -> DailyLimiter:
    return DailyLimiter(per_visitor=settings.daily_search_limit_per_visitor, total=settings.daily_search_limit_total)


@lru_cache
def get_page_fetcher() -> PoliteFetcher:
    return PoliteFetcher()


@lru_cache
def get_job_index() -> JSearchClient:
    return JSearchClient(settings.jsearch_api_key)


def use_search_quota(request: Request, limiter: DailyLimiter = Depends(get_search_limiter)) -> None:
    """Smart searches run web searches and several Claude calls, so they get their own, tighter limit."""
    _consume(limiter, request)


def use_fetch_quota(request: Request, limiter: DailyLimiter = Depends(get_fetch_limiter)) -> None:
    """Separate, more generous limit for reading job links (no Claude call)."""
    _consume(limiter, request)


def _call_claude(fn, *args):
    try:
        return fn(*args)
    except ClaudeRefusalError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except anthropic.RateLimitError as exc:
        raise HTTPException(status_code=429, detail="The AI service is busy. Please try again in a minute.") from exc
    except anthropic.APIStatusError as exc:
        raise HTTPException(status_code=502, detail=f"AI service error: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise HTTPException(status_code=503, detail="Could not reach the AI service.") from exc


async def _read_upload(file: UploadFile) -> str:
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File is too large (max 5 MB).")
    try:
        text = extract_text(file.filename or "upload", data).strip()
    except UnsupportedFileError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    if not text:
        raise HTTPException(
            status_code=422,
            detail="No text found in this file. If it's a scanned PDF, paste the text instead.",
        )
    return text


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ---------- Web app ----------

@app.get("/usage", response_model=UsageResponse)
def usage(request: Request, limiter: DailyLimiter = Depends(get_limiter)) -> UsageResponse:
    used = limiter.used(visitor_id(request))
    limit = limiter.per_visitor or None
    return UsageResponse(limit=limit, used=used, remaining=max(limit - used, 0) if limit else None)


@app.post("/resume/parse", response_model=ResumeParseResponse)
async def parse_resume(file: UploadFile = File(...)) -> ResumeParseResponse:
    """Return the text of an uploaded resume. Nothing is stored."""
    text = await _read_upload(file)
    text = text[: settings.max_resume_chars]
    return ResumeParseResponse(filename=file.filename or "resume", text=text, characters=len(text))


@app.post("/job/fetch", response_model=JobFetchResponse, dependencies=[Depends(use_fetch_quota)])
def fetch_job(req: JobFetchRequest, fetcher: JobsDBFetcher = Depends(get_job_fetcher)) -> JobFetchResponse:
    """Read one JobsDB job page from a pasted link and return its text."""
    try:
        job = fetcher.fetch(req.url)
    except UnsupportedJobUrl as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except JobFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return JobFetchResponse(
        url=job.url,
        title=job.title,
        company=job.company,
        location=job.location,
        work_type=job.work_type,
        salary=job.salary,
        text=job.as_text()[: settings.max_job_chars],
    )


@app.post("/jobs/search", dependencies=[Depends(use_search_quota)])
def search_jobs(
    req: JobSearchRequest,
    llm: LLM = Depends(get_llm),
    fetcher: PoliteFetcher = Depends(get_page_fetcher),
    index: JSearchClient = Depends(get_job_index),
) -> StreamingResponse:
    """Smart job search for any location. Streams NDJSON lines: {"type": "progress", "message"} while it works,
    then {"type": "result", "data": JobSearchResult} or {"type": "error", "message"}."""
    events: queue.Queue = queue.Queue()
    request_id = request_id_var.get()

    def worker():
        request_id_var.set(request_id)
        try:
            result = run_search(
                req.resume_text, req.location, llm, fetcher,
                lambda m: events.put({"type": "progress", "message": m}), index,
            )
            events.put({"type": "result", "data": result.model_dump()})
        except ClaudeRefusalError as exc:
            events.put({"type": "error", "message": str(exc)})
        except anthropic.APIError:
            log.exception("smart_search_failed")
            events.put({"type": "error", "message": "The AI service had a problem. Please try again in a minute."})
        except Exception:
            log.exception("smart_search_failed")
            events.put({"type": "error", "message": "Something went wrong while searching. Please try again."})
        finally:
            events.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def body():
        while (event := events.get()) is not None:
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(
        body(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.post("/analyze", response_model=FitReport, dependencies=[Depends(use_quota)])
def analyze(req: AnalyzeRequest, llm: LLM = Depends(get_llm)) -> FitReport:
    return _call_claude(llm.analyze, req.resume_text, req.job_text)


@app.post("/cover-letter/stream", dependencies=[Depends(use_quota)])
def cover_letter_stream(req: CoverLetterRequest, llm: LLM = Depends(get_llm)) -> StreamingResponse:
    """Stream the cover letter as plain text while Claude writes it."""
    chunks = llm.stream_cover_letter(req.resume_text, req.job_text, req.candidate_name)
    # Pull the first piece before responding, so API errors still become proper HTTP errors.
    first = _call_claude(next, chunks, "")

    def body():
        yield first
        try:
            yield from chunks
        except Exception:
            log.exception("cover_letter_stream_interrupted")
            yield "\n\n[The letter was interrupted. Please try again.]"

    return StreamingResponse(
        body(),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/cover-letter", response_model=CoverLetterResponse, dependencies=[Depends(use_quota)])
def cover_letter(req: CoverLetterRequest, llm: LLM = Depends(get_llm)) -> CoverLetterResponse:
    letter = _call_claude(llm.cover_letter, req.resume_text, req.job_text, req.candidate_name)
    return CoverLetterResponse(cover_letter=letter)


# ---------- Document store and RAG (can be switched off for a public demo) ----------

rag = APIRouter(tags=["documents & RAG"])


def _ingest(text: str, source: str, doc_type: DocType, store: VectorStore) -> IngestResponse:
    chunks = split_into_chunks(text, source=source, doc_type=doc_type.value)
    if not chunks:
        raise HTTPException(status_code=422, detail="The document contains no text.")
    added = store.add(chunks)
    return IngestResponse(source=source, doc_type=doc_type, chunks_added=added)


@rag.post("/documents", response_model=IngestResponse)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: DocType = Form(DocType.other),
    store: VectorStore = Depends(get_store),
) -> IngestResponse:
    text = await _read_upload(file)
    return _ingest(text, file.filename or "upload", doc_type, store)


@rag.post("/documents/text", response_model=IngestResponse)
def add_text_document(req: TextDocumentRequest, store: VectorStore = Depends(get_store)) -> IngestResponse:
    return _ingest(req.text, req.source, req.doc_type, store)


@rag.post("/ask", response_model=AskResponse, dependencies=[Depends(use_quota)])
def ask(
    req: AskRequest,
    store: VectorStore = Depends(get_store),
    llm: LLM = Depends(get_llm),
) -> AskResponse:
    chunks = store.search(req.question, k=req.k, doc_type=req.doc_type.value if req.doc_type else None)
    if not chunks:
        return AskResponse(answer="No documents have been added yet.", citations=[], sources=[])
    return _call_claude(llm.answer, req.question, chunks)


@rag.post("/extract", response_model=JobPosting, dependencies=[Depends(use_quota)])
def extract(req: ExtractRequest, llm: LLM = Depends(get_llm)) -> JobPosting:
    return _call_claude(llm.extract_job, req.job_text)


@rag.post("/match", response_model=MatchResult, dependencies=[Depends(use_quota)])
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


if settings.enable_rag_endpoints:
    app.include_router(rag)
