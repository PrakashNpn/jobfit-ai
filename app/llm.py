"""All Claude calls live here, using the official Anthropic SDK."""

from typing import Protocol

import anthropic

from .config import settings
from .schemas import AskResponse, Chunk, Citation, JobPosting, MatchResult

ANSWER_SYSTEM = (
    "You answer questions about the documents provided (resumes and job postings). "
    "Use only information found in those documents. If they don't contain the answer, "
    "say so plainly instead of guessing. Keep answers short and specific."
)

EXTRACT_SYSTEM = (
    "You extract structured data from job postings. Use only what the posting states; "
    "use null for anything not mentioned. Convert salaries to monthly Thai baht. "
    "Mark thai_language_required true only if the posting asks for Thai language ability."
)

MATCH_SYSTEM = (
    "You are a fair, practical technical recruiter. Compare the candidate's resume with "
    "the job posting. Score fit from 0 to 100, list skills the candidate clearly has that "
    "the job needs, list required skills that are missing, and flag blockers such as "
    "language, location or seniority mismatches. Base everything on the text provided."
)


class ClaudeRefusalError(RuntimeError):
    pass


class LLM(Protocol):
    def answer(self, question: str, chunks: list[Chunk]) -> AskResponse: ...

    def extract_job(self, job_text: str) -> JobPosting: ...

    def match(self, resume_text: str, job_text: str) -> MatchResult: ...


class ClaudeService:
    def __init__(self, client: anthropic.Anthropic | None = None, model: str | None = None) -> None:
        # The key comes from .env via settings; if it's not there, the SDK checks the
        # ANTHROPIC_API_KEY environment variable and `ant auth login` profiles.
        if client is None:
            key = settings.anthropic_api_key
            client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
        self.client = client
        self.model = model or settings.claude_model

    def answer(self, question: str, chunks: list[Chunk]) -> AskResponse:
        # Each chunk becomes a document block with citations enabled, so Claude's
        # answer points back to the exact text it used.
        documents = [
            {
                "type": "document",
                "source": {"type": "text", "media_type": "text/plain", "data": c.text},
                "title": f"{c.source} #{c.chunk_index}",
                "citations": {"enabled": True},
            }
            for c in chunks
        ]
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=ANSWER_SYSTEM,
            output_config={"effort": "medium"},
            # If a request is declined, the API retries it on a recommended fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": [*documents, {"type": "text", "text": question}]}],
        )
        if response.stop_reason == "refusal":
            raise ClaudeRefusalError("Claude declined to answer this question.")

        answer_parts: list[str] = []
        citations: list[Citation] = []
        for block in response.content:
            if block.type != "text":
                continue  # skip thinking and fallback blocks
            answer_parts.append(block.text)
            for cite in getattr(block, "citations", None) or []:
                citations.append(
                    Citation(source=chunks[cite.document_index].source, cited_text=cite.cited_text)
                )
        sources = sorted({c.source for c in citations})
        return AskResponse(answer="".join(answer_parts).strip(), citations=citations, sources=sources)

    def extract_job(self, job_text: str) -> JobPosting:
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=EXTRACT_SYSTEM,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": f"<job_posting>\n{job_text}\n</job_posting>"}],
            output_format=JobPosting,
        )
        return self._parsed(response)

    def match(self, resume_text: str, job_text: str) -> MatchResult:
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=MATCH_SYSTEM,
            output_config={"effort": "medium"},
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"<resume>\n{resume_text}\n</resume>\n\n"
                        f"<job_posting>\n{job_text}\n</job_posting>"
                    ),
                }
            ],
            output_format=MatchResult,
        )
        return self._parsed(response)

    @staticmethod
    def _parsed(response):
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise ClaudeRefusalError("Claude did not return a result for this request.")
        return response.parsed_output
