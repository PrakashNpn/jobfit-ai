from dataclasses import dataclass
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from .config import settings


class DocType(str, Enum):
    resume = "resume"
    job = "job"
    other = "other"


@dataclass
class Chunk:
    """One piece of a document, as stored in and returned from the vector store."""

    text: str
    source: str
    doc_type: str
    chunk_index: int
    score: float | None = None


# ---------- API requests ----------

class TextDocumentRequest(BaseModel):
    text: str = Field(min_length=1)
    source: str = Field(min_length=1, description="A name for the document, e.g. 'resume.md'")
    doc_type: DocType = DocType.other


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    k: int = Field(default=5, ge=1, le=20)
    doc_type: DocType | None = None


class ExtractRequest(BaseModel):
    job_text: str = Field(min_length=1)


class MatchRequest(BaseModel):
    job_text: str = Field(min_length=1)
    resume_text: str | None = Field(
        default=None,
        description="If omitted, the most relevant chunks of stored resumes are retrieved.",
    )


# ---------- API responses ----------

class IngestResponse(BaseModel):
    source: str
    doc_type: DocType
    chunks_added: int


class Citation(BaseModel):
    source: str
    cited_text: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    sources: list[str]


# ---------- Structured outputs from Claude ----------

class JobPosting(BaseModel):
    title: str
    company: str | None
    location: str | None
    work_type: str | None = Field(description="e.g. full-time, contract, remote, hybrid")
    salary_min_thb: int | None = Field(description="Monthly salary lower bound in THB, if stated")
    salary_max_thb: int | None = Field(description="Monthly salary upper bound in THB, if stated")
    min_years_experience: int | None
    required_skills: list[str]
    nice_to_have_skills: list[str]
    thai_language_required: bool
    english_required: bool
    summary: str = Field(description="One or two sentences describing the role")


class MatchResult(BaseModel):
    fit_score: int = Field(description="0-100: how well the candidate fits the role")
    matching_skills: list[str]
    missing_skills: list[str]
    red_flags: list[str] = Field(description="Blockers such as language, location or seniority mismatch")
    summary: str = Field(description="Two or three sentences a recruiter could read")


# ---------- Web app: fit check and cover letter ----------

class ResumeParseResponse(BaseModel):
    filename: str
    text: str
    characters: int


class AnalyzeRequest(BaseModel):
    job_text: str = Field(min_length=20, max_length=settings.max_job_chars)
    resume_text: str = Field(min_length=20, max_length=settings.max_resume_chars)


class FitReport(BaseModel):
    """Everything the web app shows after one analysis (one Claude call)."""

    job: JobPosting
    match: MatchResult
    verdict: Literal["strong", "possible", "weak"] = Field(
        description="strong = apply now; possible = apply but address the gaps; weak = probably skip"
    )
    verdict_reason: str = Field(description="One sentence explaining the verdict, written to the candidate")


class JobFetchRequest(BaseModel):
    url: str = Field(min_length=10, max_length=2000)


class JobFetchResponse(BaseModel):
    url: str
    title: str
    company: str | None
    location: str | None
    work_type: str | None
    salary: str | None
    text: str = Field(description="The full job posting as plain text, ready for /analyze")


class CoverLetterRequest(AnalyzeRequest):
    candidate_name: str | None = Field(default=None, max_length=100)


class CoverLetterResponse(BaseModel):
    cover_letter: str


class UsageResponse(BaseModel):
    limit: int | None = Field(description="Daily analyses allowed per visitor; null means unlimited")
    used: int
    remaining: int | None


# ---------- Smart job search ----------


class SearchPlan(BaseModel):
    """What Claude thinks this candidate should search for, and where."""

    roles: list[str] = Field(description="2 or 3 job titles that best fit the resume, most suitable first")
    seniority: str = Field(description="junior, mid-level or senior, judged from the resume")
    location_label: str = Field(description="The location written clearly, e.g. 'Bangkok, Thailand' or 'Remote'")
    country_code: str | None = Field(description="ISO 3166-1 alpha-2 country code, lowercase (e.g. 'th'); null for remote")
    job_sites: list[str] = Field(
        description="3 to 5 job-board domains most used in that location, local boards first, e.g. 'th.jobsdb.com'"
    )


class RankedCard(BaseModel):
    """One job card from a results page, cleaned up and scored against the resume."""

    card_id: str
    title: str = Field(description="The job title only, without company or location")
    company: str | None
    location: str | None
    posted: str | None = Field(description="When it was posted, as shown on the card, e.g. '2 days ago'")
    age_days: int | None = Field(description="Approximate days since it was posted; null if the card doesn't say")
    fit_score: int = Field(description="0-100")
    verdict: Literal["strong", "possible", "weak"]
    reason: str = Field(description="At most 20 words, addressed to the candidate as 'you'")
    deal_breakers: list[str] = Field(description="Short tags; empty if none")


class RankedCards(BaseModel):
    jobs: list[RankedCard]


class FoundJob(BaseModel):
    url: str
    site: str
    title: str
    company: str | None = None
    location: str | None = None
    posted: str | None = None
    fit_score: int
    verdict: Literal["strong", "possible", "weak"]
    reason: str
    deal_breakers: list[str]
    summary: str = Field(description="The text shown on the results page, used for a quick fit check")


class SearchLink(BaseModel):
    role: str
    site: str
    url: str


class JobSearchRequest(BaseModel):
    resume_text: str = Field(min_length=20, max_length=settings.max_resume_chars)
    location: str = Field(min_length=2, max_length=80)


class JobSearchResult(BaseModel):
    location_label: str
    plan: SearchPlan
    jobs: list[FoundJob]
    pages_read: list[str]
    pages_skipped: int = Field(description="Results pages we didn't read (robots.txt or the site blocked us)")
    index_results: int = Field(default=0, description="Jobs that came from the job-search index (JSearch)")
    search_links: list[SearchLink]
