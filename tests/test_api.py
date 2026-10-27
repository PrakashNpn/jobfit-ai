"""API tests with an in-memory store and a fake LLM: no database or API key needed."""

import json

import pytest
from fastapi.testclient import TestClient

from app.jobfetch import FetchedJob, JobFetchError, canonical_job_url
from app.limits import DailyLimiter
from app.llm import ClaudeRefusalError, Discovery
from app.main import (
    app,
    get_fetch_limiter,
    get_job_fetcher,
    get_job_index,
    get_page_fetcher,
    get_limiter,
    get_llm,
    get_search_limiter,
    get_store,
)
from app.schemas import (
    AskResponse,
    Chunk,
    Citation,
    FitReport,
    JobPosting,
    RankedCard,
    MatchResult,
    SearchPlan,
)


class FakeStore:
    def __init__(self):
        self.chunks: list[Chunk] = []

    def add(self, chunks):
        self.chunks.extend(chunks)
        return len(chunks)

    def search(self, query, k, doc_type=None):
        hits = [c for c in self.chunks if doc_type is None or c.doc_type == doc_type]
        return hits[:k]


class FakeLLM:
    refuse = False

    def answer(self, question, chunks):
        if self.refuse:
            raise ClaudeRefusalError("declined")
        return AskResponse(
            answer=f"Answer to: {question}",
            citations=[Citation(source=chunks[0].source, cited_text=chunks[0].text[:20])],
            sources=[chunks[0].source],
        )

    def extract_job(self, job_text):
        return JobPosting(
            title="AI Engineer",
            company="Example Co",
            location="Bangkok",
            work_type="full-time",
            salary_min_thb=40000,
            salary_max_thb=50000,
            min_years_experience=2,
            required_skills=["Python", "RAG"],
            nice_to_have_skills=[],
            thai_language_required=False,
            english_required=True,
            summary="Builds LLM features.",
        )

    def match(self, resume_text, job_text):
        self.last_resume = resume_text
        return MatchResult(
            fit_score=80,
            matching_skills=["Python"],
            missing_skills=["Go"],
            red_flags=[],
            summary="Good fit.",
        )

    def analyze(self, resume_text, job_text):
        return FitReport(
            job=self.extract_job(job_text),
            match=self.match(resume_text, job_text),
            verdict="strong",
            verdict_reason="You match most requirements.",
        )

    def cover_letter(self, resume_text, job_text, candidate_name):
        return f"Dear Hiring Team,\n\n...\n\nBest regards,\n{candidate_name or 'Candidate'}"

    def plan_search(self, resume_text, location):
        return SearchPlan(
            roles=["Full Stack Developer", "AI Engineer"], seniority="mid-level",
            location_label="Bangkok, Thailand", country_code="th", job_sites=["th.jobsdb.com", "linkedin.com"],
        )

    def discover(self, plan, on_progress):
        on_progress("Searching: Full Stack Developer jobs Bangkok")
        return Discovery(results=[
            ("https://th.jobsdb.com/full-stack-developer-jobs/in-Bangkok", "Full Stack Developer jobs"),
            ("https://www.linkedin.com/jobs/view/123", "AI Engineer at Beta"),
        ])

    def rank_cards(self, resume_text, cards, location_label):
        return [
            RankedCard(card_id=card_id, title=text.split("\n")[0], company="Acme", location="Bangkok", posted="2 days ago",
                       age_days=2, fit_score=50 + 10 * i, verdict="possible", reason="ok", deal_breakers=[])
            for i, (card_id, text) in enumerate(cards)
        ]

    def stream_cover_letter(self, resume_text, job_text, candidate_name):
        if self.refuse:
            raise ClaudeRefusalError("declined")
        yield "Dear Hiring Team,"
        yield "\n\nI am applying..."
        yield f"\n\nBest regards,\n{candidate_name or 'Candidate'}"


LISTING_HTML = """<html><body>
<a href="/job/95000111">Full Stack Developer</a><span>Acme · Bangkok · Listed 2 days ago</span>
<a href="/job/95000222">Web Developer</a><span>Beta · Bangkok · Listed 3 days ago</span>
<a href="/job/95000333">QA Engineer</a><span>Gamma · Bangkok · Listed 1 day ago</span>
</body></html>"""


class FakePageFetcher:
    def get_html(self, url, respect_robots=True):
        return url, LISTING_HTML


class FakeIndex:
    available = False


class FakeFetcher:
    def fetch(self, raw_url):
        url = canonical_job_url(raw_url)  # real validation, fake network
        if url.endswith("/job/99999"):
            raise JobFetchError("This job is no longer advertised on JobsDB.")
        return FetchedJob(
            url=url,
            title="AI Engineer",
            company="Example Co",
            location="Bangkok",
            work_type="Full time",
            salary=None,
            description="Requires Python and RAG.",
        )


RESUME = "Full-stack developer with Python, React and RAG experience."
JOB = "AI Engineer in Bangkok. Requires Python and RAG. 40-50k THB."


@pytest.fixture
def client():
    store, llm = FakeStore(), FakeLLM()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_limiter] = lambda: DailyLimiter(per_visitor=0, total=0)
    app.dependency_overrides[get_fetch_limiter] = lambda: DailyLimiter(per_visitor=0, total=0)
    app.dependency_overrides[get_job_fetcher] = lambda: FakeFetcher()
    app.dependency_overrides[get_search_limiter] = lambda: DailyLimiter(per_visitor=0, total=0)
    app.dependency_overrides[get_page_fetcher] = lambda: FakePageFetcher()
    app.dependency_overrides[get_job_index] = lambda: FakeIndex()
    with TestClient(app) as c:
        c.store, c.llm = store, llm
        yield c
    app.dependency_overrides.clear()


# ---------- Web app endpoints ----------

def test_parse_resume_returns_text_without_storing(client):
    res = client.post("/resume/parse", files={"file": ("cv.md", RESUME.encode(), "text/markdown")})
    assert res.status_code == 200
    assert res.json()["text"] == RESUME
    assert client.store.chunks == []


def test_parse_resume_rejects_empty_file(client):
    res = client.post("/resume/parse", files={"file": ("cv.txt", b"   ", "text/plain")})
    assert res.status_code == 422


def test_analyze(client):
    res = client.post("/analyze", json={"resume_text": RESUME, "job_text": JOB})
    assert res.status_code == 200
    body = res.json()
    assert body["verdict"] == "strong"
    assert body["match"]["fit_score"] == 80
    assert body["job"]["thai_language_required"] is False


def test_analyze_rejects_too_short_input(client):
    res = client.post("/analyze", json={"resume_text": "hi", "job_text": JOB})
    assert res.status_code == 422


def test_cover_letter_uses_name(client):
    res = client.post(
        "/cover-letter", json={"resume_text": RESUME, "job_text": JOB, "candidate_name": "Thi Han"}
    )
    assert res.status_code == 200
    assert res.json()["cover_letter"].endswith("Thi Han")


def test_cover_letter_stream(client):
    body = {"resume_text": RESUME, "job_text": JOB, "candidate_name": "Thi Han"}
    with client.stream("POST", "/cover-letter/stream", json=body) as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/plain")
        text = "".join(res.iter_text())
    assert text.startswith("Dear Hiring Team,")
    assert text.endswith("Thi Han")


def test_cover_letter_stream_refusal_is_an_http_error(client):
    client.llm.refuse = True
    res = client.post("/cover-letter/stream", json={"resume_text": RESUME, "job_text": JOB})
    assert res.status_code == 422


def test_every_response_has_a_request_id(client):
    res = client.get("/health")
    assert len(res.headers["x-request-id"]) == 12
    assert client.get("/health", headers={"X-Request-ID": "abc123"}).headers["x-request-id"] == "abc123"


def test_daily_limit_per_visitor(client):
    limiter = DailyLimiter(per_visitor=2, total=0)
    app.dependency_overrides[get_limiter] = lambda: limiter
    body = {"resume_text": RESUME, "job_text": JOB}
    assert client.post("/analyze", json=body).status_code == 200
    assert client.post("/cover-letter", json=body).status_code == 200
    blocked = client.post("/analyze", json=body)
    assert blocked.status_code == 429
    assert "free analyses" in blocked.json()["detail"]
    assert client.get("/usage").json() == {"limit": 2, "used": 2, "remaining": 0}


def test_daily_limit_total_applies_across_visitors(client):
    limiter = DailyLimiter(per_visitor=0, total=1)
    app.dependency_overrides[get_limiter] = lambda: limiter
    body = {"resume_text": RESUME, "job_text": JOB}
    assert client.post("/analyze", json=body, headers={"x-forwarded-for": "1.1.1.1"}).status_code == 200
    assert client.post("/analyze", json=body, headers={"x-forwarded-for": "2.2.2.2"}).status_code == 429


def test_fetch_job_from_link(client):
    res = client.post("/job/fetch", json={"url": "https://th.jobsdb.com/job/95333770/apply?sol=x"})
    assert res.status_code == 200
    body = res.json()
    assert body["url"] == "https://th.jobsdb.com/job/95333770"
    assert body["text"].startswith("AI Engineer\nExample Co\nBangkok · Full time")


def test_fetch_job_rejects_other_sites(client):
    res = client.post("/job/fetch", json={"url": "https://www.linkedin.com/jobs/view/123"})
    assert res.status_code == 422
    assert "JobsDB" in res.json()["detail"]


def test_fetch_job_reports_expired_post(client):
    res = client.post("/job/fetch", json={"url": "https://th.jobsdb.com/job/99999"})
    assert res.status_code == 502
    assert "no longer advertised" in res.json()["detail"]


def test_fetch_does_not_use_analysis_quota(client):
    analysis = DailyLimiter(per_visitor=1, total=0)
    app.dependency_overrides[get_limiter] = lambda: analysis
    client.post("/job/fetch", json={"url": "https://th.jobsdb.com/job/95333770"})
    assert client.post("/analyze", json={"resume_text": RESUME, "job_text": JOB}).status_code == 200


def search_events(client, location="Bangkok"):
    with client.stream("POST", "/jobs/search", json={"resume_text": RESUME, "location": location}) as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("application/x-ndjson")
        return [json.loads(line) for line in res.iter_lines() if line]


def test_job_search_streams_progress_then_ranked_result(client):
    events = search_events(client)
    progress = [e["message"] for e in events if e["type"] == "progress"]
    assert any(m.startswith("Searching:") for m in progress)
    result = events[-1]
    assert result["type"] == "result"
    jobs = result["data"]["jobs"]
    assert [j["fit_score"] for j in jobs] == sorted((j["fit_score"] for j in jobs), reverse=True)
    assert {j["url"] for j in jobs} >= {"https://th.jobsdb.com/job/95000111", "https://www.linkedin.com/jobs/view/123"}
    assert result["data"]["pages_read"] == ["https://th.jobsdb.com/full-stack-developer-jobs/in-Bangkok"]


def test_job_search_errors_arrive_as_an_event(client):
    def boom(resume_text, location):
        raise ClaudeRefusalError("declined")

    client.llm.plan_search = boom
    events = search_events(client)
    assert events[-1] == {"type": "error", "message": "declined"}


def test_job_search_has_its_own_daily_limit(client):
    limiter = DailyLimiter(per_visitor=1, total=0)
    app.dependency_overrides[get_search_limiter] = lambda: limiter
    search_events(client)
    assert client.post("/jobs/search", json={"resume_text": RESUME, "location": "Bangkok"}).status_code == 429
    assert client.post("/analyze", json={"resume_text": RESUME, "job_text": JOB}).status_code == 200


def test_usage_unlimited_by_default(client):
    assert client.get("/usage").json() == {"limit": None, "used": 0, "remaining": None}


# ---------- Document store and RAG ----------


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_add_text_document_chunks_and_stores(client):
    res = client.post(
        "/documents/text",
        json={"text": "Python developer. " * 200, "source": "resume.md", "doc_type": "resume"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["chunks_added"] > 1
    assert all(c.doc_type == "resume" for c in client.store.chunks)


def test_upload_rejects_unsupported_file(client):
    res = client.post("/documents", files={"file": ("photo.png", b"\x89PNG", "image/png")})
    assert res.status_code == 415


def test_upload_markdown(client):
    res = client.post(
        "/documents",
        files={"file": ("job.md", b"# AI Engineer\nWe need RAG experience.", "text/markdown")},
        data={"doc_type": "job"},
    )
    assert res.status_code == 200
    assert res.json()["doc_type"] == "job"


def test_ask_without_documents(client):
    res = client.post("/ask", json={"question": "What skills?"})
    assert res.status_code == 200
    assert res.json()["sources"] == []


def test_ask_returns_citations(client):
    client.post("/documents/text", json={"text": "Knows FastAPI.", "source": "cv.md", "doc_type": "resume"})
    res = client.post("/ask", json={"question": "Does the candidate know FastAPI?"})
    assert res.status_code == 200
    assert res.json()["sources"] == ["cv.md"]


def test_ask_refusal_returns_422(client):
    client.post("/documents/text", json={"text": "Some text.", "source": "a.md"})
    client.llm.refuse = True
    res = client.post("/ask", json={"question": "Anything"})
    assert res.status_code == 422


def test_extract(client):
    res = client.post("/extract", json={"job_text": "AI Engineer in Bangkok, 40-50k THB"})
    assert res.status_code == 200
    assert res.json()["thai_language_required"] is False


def test_match_needs_a_resume(client):
    res = client.post("/match", json={"job_text": "Need Python"})
    assert res.status_code == 422


def test_match_retrieves_stored_resume(client):
    client.post("/documents/text", json={"text": "Python and RAG.", "source": "cv.md", "doc_type": "resume"})
    client.post("/documents/text", json={"text": "Unrelated job.", "source": "job.md", "doc_type": "job"})
    res = client.post("/match", json={"job_text": "Need Python"})
    assert res.status_code == 200
    assert res.json()["fit_score"] == 80
    assert "Unrelated job" not in client.llm.last_resume
