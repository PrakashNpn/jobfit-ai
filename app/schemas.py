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


class CoverLetterRequest(AnalyzeRequest):
    candidate_name: str | None = Field(default=None, max_length=100)


class CoverLetterResponse(BaseModel):
    cover_letter: str


class UsageResponse(BaseModel):
    limit: int | None = Field(description="Daily analyses allowed per visitor; null means unlimited")
    used: int
    remaining: int | None
