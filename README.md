# JobFit AI

A FastAPI service that reads resumes and job postings, answers questions about them with **retrieval-augmented generation (RAG)**, extracts job postings into **structured JSON**, and scores how well a resume fits a job.

Built with **Python, FastAPI, LangChain, PostgreSQL + pgvector, and Claude**.

## What it does

| Endpoint | Purpose |
|---|---|
| `POST /documents` | Upload a PDF, Markdown or text file → split into chunks → embed → store in pgvector |
| `POST /documents/text` | Same, for raw text in a JSON body |
| `POST /ask` | Ask a question → retrieve the most relevant chunks → Claude answers **with citations** pointing to the exact source text |
| `POST /extract` | Job posting text → validated `JobPosting` JSON (title, salary in THB, required skills, years, Thai language required, …) |
| `POST /match` | Job posting (+ optional resume text) → fit score, matching and missing skills, red flags. With no resume text, it retrieves the most relevant chunks of stored resumes. |

Interactive docs are at `http://localhost:8000/docs` once the server is running.

## Architecture

```mermaid
flowchart LR
    U[Client] -->|upload| API[FastAPI]
    API --> S[LangChain text splitter]
    S --> E[FastEmbed embeddings<br/>bge-small-en, runs locally]
    E --> DB[(PostgreSQL + pgvector)]
    U -->|ask / match| API
    API -->|similarity search| DB
    DB -->|top-k chunks| API
    API -->|chunks as cited documents| C[Claude API]
    C -->|answer + citations / structured JSON| API
```

**Design choices**
- **Citations, not just answers.** Retrieved chunks are sent to Claude as document blocks with citations enabled, so every answer links back to the text it came from.
- **Structured output with Pydantic.** `/extract` and `/match` use the Anthropic SDK's `messages.parse` with Pydantic models, so responses are validated objects, not free text to be parsed.
- **Local embeddings.** FastEmbed runs the embedding model on CPU: no extra API key and no cost per document.
- **Refusal handling.** If Claude declines a request, the API returns a clear 422 instead of an empty answer. `/ask` also opts into server-side fallbacks.
- **Testable by design.** The vector store and LLM are FastAPI dependencies, so tests swap in fakes and run without a database or API key.

## Quick start

Requirements: Python 3.12, Docker, and an [Anthropic API key](https://console.anthropic.com/).

```bash
# 1. Start PostgreSQL with pgvector
docker compose up -d

# 2. Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# 3. Configure
cp .env.example .env        # then put your ANTHROPIC_API_KEY in .env

# 4. Run
uvicorn app.main:app --reload
```

The first request downloads the embedding model (about 100 MB), so it takes a little longer.

**No Docker? Use Supabase.** Any Postgres with pgvector works. Create a Supabase project, enable the `vector` extension (Database → Extensions), and set `DATABASE_URL` in `.env` to the Session pooler connection string, starting with `postgresql+psycopg://`. Then skip step 1.

## Try it

```bash
# Add the sample resume and job postings
curl -F "file=@data/resume_alex_tan.md" -F "doc_type=resume" localhost:8000/documents
curl -F "file=@data/job_ai_engineer.md" -F "doc_type=job" localhost:8000/documents
curl -F "file=@data/job_backend_go.md" -F "doc_type=job" localhost:8000/documents

# Ask a question (answer comes with citations)
curl -X POST localhost:8000/ask -H "Content-Type: application/json" \
  -d '{"question": "Which job requires Thai language?"}'

# Extract a job posting into JSON
curl -X POST localhost:8000/extract -H "Content-Type: application/json" \
  -d "{\"job_text\": $(jq -Rs . < data/job_ai_engineer.md)}"

# Score the stored resume against a job
curl -X POST localhost:8000/match -H "Content-Type: application/json" \
  -d "{\"job_text\": $(jq -Rs . < data/job_ai_engineer.md)}"
```

## Evaluation

`evals/run_eval.py` measures quality on the sample data:
- **RAG answers:** 10 questions, each graded by required keywords, including two questions the documents *can't* answer, to check that the model says so instead of guessing.
- **Extraction:** 3 job postings, checking salary, years of experience and Thai-language fields against expected values.

```bash
python -m evals.run_eval --ingest   # first run loads data/ into the store
python -m evals.run_eval            # later runs
```

Results are printed and saved to `evals/results/`. Each run makes about 13 Claude API calls.

**Latest results** (Claude Sonnet 5.5, Oct 2026):

| Check | Score |
|---|---|
| RAG answers (10 questions, incl. 2 the documents can't answer) | **10/10 (100%)** |
| Structured extraction (3 job postings) | **3/3 (100%)** |

The first evaluation run was useful: it showed that the job postings had never been ingested (the model correctly answered "the documents only contain a resume" instead of guessing), and it exposed two weak spots in the keyword grader, which were fixed before this run.

## Tests

```bash
pytest -q
```

Tests use an in-memory store and a fake LLM, so they need no database or API key. GitHub Actions runs them on every push.

## Configuration

| Variable | Default |
|---|---|
| `ANTHROPIC_API_KEY` | required |
| `CLAUDE_MODEL` | `claude-sonnet-5-5` |
| `DATABASE_URL` | `postgresql+psycopg://jobfit:jobfit@localhost:6024/jobfit` |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` |

## Project structure

```
app/
  main.py      FastAPI routes and error handling
  llm.py       Claude calls: cited answers, structured extraction, matching
  store.py     LangChain PGVectorStore + FastEmbed embeddings
  ingest.py    PDF/Markdown text extraction and chunking
  schemas.py   Pydantic request/response and structured-output models
evals/         Evaluation cases and runner
data/          Fictional sample resume and job postings
tests/         API and ingestion tests
```

## Roadmap

- Deduplicate documents on re-upload
- Hybrid search (keyword + vector)
- A small Next.js front end
- LLM-graded evaluation alongside keyword checks
