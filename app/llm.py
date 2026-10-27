"""All Claude calls live here, using the official Anthropic SDK."""

import re
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import anthropic

from .config import settings
from .observability import log, log_claude_usage
from .schemas import (
    AskResponse,
    Chunk,
    Citation,
    FitReport,
    JobPosting,
    MatchResult,
    RankedCard,
    RankedCards,
    SearchPlan,
)

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

ANALYZE_SYSTEM = (
    "You help a job seeker decide whether to apply for a job. Do two things:\n"
    "1. Extract the job's key facts. Use only what the posting states and null for anything "
    "not mentioned. Convert salaries to monthly Thai baht. Mark thai_language_required true "
    "only if the posting asks for Thai language ability.\n"
    "2. Compare the candidate's resume with the job like a fair, practical recruiter: score fit "
    "from 0 to 100, list required skills the resume clearly shows, list required skills it "
    "doesn't show, and flag blockers such as language, location, seniority or salary mismatch.\n"
    "Then give a verdict (strong, possible or weak) with one sentence addressed to the candidate "
    "as 'you'. Base everything on the text provided; never assume skills the resume doesn't show."
)

PLAN_SYSTEM = (
    "You plan a job search. From the resume and the location, choose:\n"
    "- roles: the 2 or 3 job titles the candidate is most likely to be hired for now, written the way "
    "employers title job ads (e.g. 'Full Stack Developer', 'AI Engineer'); best fit first; no seniority words.\n"
    "- job_sites: the 3 to 5 job-board domains most used for these roles in that location, local boards first "
    "(e.g. Thailand: th.jobsdb.com, jobthai.com; Singapore: sg.jobstreet.com, mycareersfuture.gov.sg; UAE: bayt.com, "
    "naukrigulf.com; India: naukri.com; Australia: seek.com.au; Germany: stepstone.de; remote: weworkremotely.com, "
    "remoteok.com, wellfound.com). Use bare domains. Always include linkedin.com last.\n"
    "- location_label: the location written clearly; country_code: its ISO 3166-1 alpha-2 code in lowercase "
    "(null for remote). Base roles and seniority on the resume only."
)

DISCOVER_SYSTEM = (
    "You find job-board pages that list current job openings. For each job title, search the given job sites "
    "with queries like '<job title> jobs <city>' so the results include the site's own search-results pages "
    "for that title and location (pages that list many jobs), plus individual postings. One search per job "
    "title per site, most important sites first. Do not answer with prose; just run the searches."
)

RANK_SYSTEM = (
    "You screen job postings for one candidate, like a fair, practical recruiter. Each job is a card copied "
    "from a job board's results page, so it may be messy or mixed with page text. For every card:\n"
    "- Clean up the title (job title only), company, location and when it was posted, as shown on the card; "
    "use null if not shown.\n"
    "- Give a fit score from 0 to 100 and a verdict (strong = apply now, possible = apply but address gaps, "
    "weak = probably skip), plus one sentence of at most 20 words addressed to the candidate as 'you'.\n"
    "- deal_breakers: short tags only for requirements the candidate clearly does NOT meet and that would "
    "likely get them rejected: a required language the resume doesn't show, far more years than they have, "
    "citizenship or clearance, a core technology they lack, or a job clearly located in a different city or "
    "country than the one they are searching. Never tag a requirement they meet. Empty list if none.\n"
    "Judge only what the card shows; don't invent requirements. If the card doesn't show the tech stack or "
    "requirements, the fit is uncertain: score at most 65 and say what to check. Return one result for every card_id."
)

RANK_BATCH_SIZE = 3  # small batches run in parallel: total time ≈ one batch
# Haiku 5.5 takes the basic web search tool; the newer dynamic-filtering version is Opus/Sonnet only.
WEB_SEARCH_TOOL = "web_search_20250305"
MAX_SEARCHES = 4


@dataclass
class Discovery:
    results: list[tuple[str, str]]  # (url, title) of every search result, in order

COVER_LETTER_SYSTEM = (
    "You write short, professional cover letters for job applications. Rules:\n"
    "- 120 to 170 words, plain text, no markdown, no placeholders in square brackets.\n"
    "- Open with the role and why the candidate fits; then two or three concrete achievements "
    "from the resume that match the job; then a one-line close.\n"
    "- Only mention skills and experience that appear in the resume. Never invent numbers, "
    "employers or skills.\n"
    "- Address it to 'Dear Hiring Team,' and sign off with 'Best regards,' followed by the "
    "candidate's name if given, otherwise the name from the resume.\n"
    "Output only the letter."
)


class ClaudeRefusalError(RuntimeError):
    pass


class LLM(Protocol):
    def answer(self, question: str, chunks: list[Chunk]) -> AskResponse: ...

    def extract_job(self, job_text: str) -> JobPosting: ...

    def match(self, resume_text: str, job_text: str) -> MatchResult: ...

    def analyze(self, resume_text: str, job_text: str) -> FitReport: ...

    def cover_letter(self, resume_text: str, job_text: str, candidate_name: str | None) -> str: ...

    def stream_cover_letter(
        self, resume_text: str, job_text: str, candidate_name: str | None
    ) -> Iterator[str]: ...

    def plan_search(self, resume_text: str, location: str) -> SearchPlan: ...

    def discover(self, plan: SearchPlan, on_progress: Callable[[str], None]) -> "Discovery": ...

    def rank_cards(self, resume_text: str, cards: list[tuple[str, str]], location_label: str) -> list[RankedCard]: ...


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
        started = time.perf_counter()
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=ANSWER_SYSTEM,
            output_config={"effort": "medium"},
            messages=[{"role": "user", "content": [*documents, {"type": "text", "text": question}]}],
            **_fallback_args(self.model),
        )
        log_claude_usage("answer", self.model, response.usage, started)
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
        started = time.perf_counter()
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=EXTRACT_SYSTEM,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": f"<job_posting>\n{job_text}\n</job_posting>"}],
            output_format=JobPosting,
        )
        log_claude_usage("extract_job", self.model, response.usage, started)
        return self._parsed(response)

    def match(self, resume_text: str, job_text: str) -> MatchResult:
        started = time.perf_counter()
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
        log_claude_usage("match", self.model, response.usage, started)
        return self._parsed(response)

    def analyze(self, resume_text: str, job_text: str) -> FitReport:
        started = time.perf_counter()
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=ANALYZE_SYSTEM,
            output_config={"effort": "medium"},
            messages=[{"role": "user", "content": _resume_and_job(resume_text, job_text)}],
            output_format=FitReport,
        )
        log_claude_usage("analyze", self.model, response.usage, started)
        return self._parsed(response)

    def cover_letter(self, resume_text: str, job_text: str, candidate_name: str | None) -> str:
        content = _resume_and_job(resume_text, job_text)
        if candidate_name:
            content += f"\n\nCandidate name: {candidate_name}"
        started = time.perf_counter()
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=COVER_LETTER_SYSTEM,
            output_config={"effort": "low"},  # writing, not reasoning: ~3x faster first words
            messages=[{"role": "user", "content": content}],
            **_fallback_args(self.model),
        )
        log_claude_usage("cover_letter", self.model, response.usage, started)
        if response.stop_reason == "refusal":
            raise ClaudeRefusalError("Claude declined to write this cover letter.")
        letter = "".join(block.text for block in response.content if block.type == "text").strip()
        if not letter:
            raise ClaudeRefusalError("Claude did not return a cover letter.")
        return letter

    def stream_cover_letter(self, resume_text: str, job_text: str, candidate_name: str | None) -> Iterator[str]:
        """Yield the cover letter text as Claude writes it."""
        content = _resume_and_job(resume_text, job_text)
        if candidate_name:
            content += f"\n\nCandidate name: {candidate_name}"
        started = time.perf_counter()
        with self.client.beta.messages.stream(
            model=self.model,
            max_tokens=16000,
            system=COVER_LETTER_SYSTEM,
            output_config={"effort": "low"},  # writing, not reasoning: ~3x faster first words
            messages=[{"role": "user", "content": content}],
            **_fallback_args(self.model),
        ) as stream:
            yield from stream.text_stream
            final = stream.get_final_message()
        log_claude_usage("cover_letter_stream", self.model, final.usage, started)
        if final.stop_reason == "refusal":
            raise ClaudeRefusalError("Claude stopped before finishing the cover letter.")

    def plan_search(self, resume_text: str, location: str) -> SearchPlan:
        started = time.perf_counter()
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=4000,
            system=PLAN_SYSTEM,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": f"<resume>\n{resume_text}\n</resume>\n\nLocation: {location}"}],
            output_format=SearchPlan,
        )
        log_claude_usage("plan_search", self.model, response.usage, started)
        return self._parsed(response)

    def discover(self, plan: SearchPlan, on_progress: Callable[[str], None]) -> "Discovery":
        """Web-search the planned job sites and collect result pages, reporting each search as it runs."""
        sites = plan.job_sites[:5]
        try:
            return self._discover(plan, sites, on_progress)
        except anthropic.BadRequestError as exc:
            # The search tool refuses some domains (sites that block Anthropic's crawler). Drop them and retry.
            refused = set(re.findall(r"'([^']+)'", str(exc).split("not accessible", 1)[-1])) if "not accessible" in str(exc) else set()
            remaining = [s for s in sites if s not in refused]
            if not refused or not remaining:
                raise
            log.info("discover_retry", extra={"fields": {"refused": sorted(refused)}})
            return self._discover(plan, remaining, on_progress)

    def _discover(self, plan: SearchPlan, sites: list[str], on_progress: Callable[[str], None]) -> "Discovery":
        started = time.perf_counter()
        with self.client.messages.stream(
            model=self.model,
            max_tokens=4000,
            system=DISCOVER_SYSTEM,
            output_config={"effort": "low"},
            tools=[{"type": WEB_SEARCH_TOOL, "name": "web_search", "max_uses": MAX_SEARCHES, "allowed_domains": sites}],
            messages=[
                {
                    "role": "user",
                    "content": f"Job titles: {', '.join(plan.roles[:2])}\nLocation: {plan.location_label}\n"
                    f"Job sites: {', '.join(sites)}",
                }
            ],
        ) as stream:
            for event in stream:
                block = getattr(event, "content_block", None)
                if event.type == "content_block_stop" and getattr(block, "type", None) == "server_tool_use":
                    tool_input = block.input if isinstance(block.input, dict) else {}
                    query = tool_input.get("query")
                    if query:
                        on_progress(f"Searching: {query}")
            final = stream.get_final_message()
        log_claude_usage("discover", self.model, final.usage, started)

        results: list[tuple[str, str]] = []
        for block in final.content:
            if block.type == "web_search_tool_result" and isinstance(block.content, list):
                results += [(r.url, r.title or "") for r in block.content]
        return Discovery(results=list(dict.fromkeys(results)))

    def rank_cards(self, resume_text: str, cards: list[tuple[str, str]], location_label: str) -> list[RankedCard]:
        """Score (card_id, card_text) pairs in small parallel batches; returns one result per known card_id."""
        batches = [cards[i : i + RANK_BATCH_SIZE] for i in range(0, len(cards), RANK_BATCH_SIZE)]
        with ThreadPoolExecutor(max_workers=max(1, min(len(batches), 10))) as pool:
            results = pool.map(lambda batch: self._rank_batch_safely(resume_text, batch, location_label), batches)
        return [card for batch in results for card in batch]

    def _rank_batch_safely(self, resume_text: str, cards: list[tuple[str, str]], location_label: str) -> list[RankedCard]:
        """One failed batch shouldn't sink the whole search: retry once, then skip those cards."""
        for attempt in (1, 2):
            try:
                return self._rank_batch(resume_text, cards, location_label)
            except Exception:
                log.exception("rank_batch_failed", extra={"fields": {"attempt": attempt, "cards": len(cards)}})
        return []

    def _rank_batch(self, resume_text: str, cards: list[tuple[str, str]], location_label: str) -> list[RankedCard]:
        # Give Claude short numbers instead of real IDs, then map them back: long IDs get miscopied.
        numbered = {str(n): card_id for n, (card_id, _) in enumerate(cards, start=1)}
        body = "\n\n".join(
            f'<card card_id="{n}">\n{text}\n</card>' for n, (_, text) in enumerate(cards, start=1)
        )
        started = time.perf_counter()
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=8000,
            system=RANK_SYSTEM,
            output_config={"effort": "low"},
            messages=[
                {
                    "role": "user",
                    "content": f"The candidate is searching for jobs in: {location_label}\n\n"
                    f"<resume>\n{resume_text}\n</resume>\n\n<cards>\n{body}\n</cards>",
                }
            ],
            output_format=RankedCards,
        )
        log_claude_usage("rank_cards", self.model, response.usage, started)
        ranked = []
        for card in self._parsed(response).jobs:
            real_id = numbered.get(card.card_id.strip())
            if real_id:
                ranked.append(card.model_copy(update={"card_id": real_id}))
        return ranked

    @staticmethod
    def _parsed(response):
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise ClaudeRefusalError("Claude did not return a result for this request.")
        return response.parsed_output


def _resume_and_job(resume_text: str, job_text: str) -> str:
    return f"<resume>\n{resume_text}\n</resume>\n\n<job_posting>\n{job_text}\n</job_posting>"


# Models that accept server-side refusal fallbacks (Haiku models don't).
_FALLBACK_MODELS = ("claude-fable-5", "claude-opus-5", "claude-sonnet-5-5")


def _fallback_args(model: str) -> dict:
    """If a request is declined, the API retries it on a recommended fallback model."""
    if model.startswith(_FALLBACK_MODELS):
        return {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    return {}

