"""Smart job search: Claude plans and discovers, our code reads, Claude ranks.

1. Plan     - Claude picks job titles and the local job sites for any location.
2. Discover - Claude web-searches those sites for their results pages (pages listing many jobs).
3. Read     - we open up to 3 results pages, only where robots.txt allows, and cut them into job cards.
4. Rank     - Claude scores every card against the resume, in parallel batches.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus, urlparse

from .cards import RawCard, extract_cards, is_posting_url
from .jsearch import JSearchClient
from .llm import LLM
from .observability import log_event
from .schemas import FoundJob, JobSearchResult, SearchLink
from .webfetch import FetchBlocked, FetchFailed, PoliteFetcher

MAX_PAGES_TO_TRY = 5
MAX_PAGES_TO_READ = 3
MIN_CARDS_PER_PAGE = 3
MAX_JOBS = 30
MAX_LEADS = 6  # single postings found directly in search results (e.g. LinkedIn), not opened
MAX_AGE_DAYS = 60  # older postings are probably filled
ENOUGH_FROM_BOARDS = 15  # below this, also ask the job-search index


def site_of(url: str) -> str:
    return (urlparse(url).hostname or "").removeprefix("www.")


def _on_planned_site(url: str, sites: list[str]) -> bool:
    host = site_of(url)
    return any(host == s.removeprefix("www.") or host.endswith("." + s.removeprefix("www.")) for s in sites)


def _interleave_by_site(urls: list[str]) -> list[str]:
    """Take results pages from different sites in turn, so one board doesn't fill every slot."""
    by_site: dict[str, list[str]] = {}
    for url in dict.fromkeys(urls):
        by_site.setdefault(site_of(url), []).append(url)
    ordered = []
    while any(by_site.values()):
        for queue_ in by_site.values():
            if queue_:
                ordered.append(queue_.pop(0))
    return ordered


def _read_page(fetcher: PoliteFetcher, url: str) -> tuple[str, list[RawCard] | None, str | None]:
    try:
        final_url, html = fetcher.get_html(url)
        return url, extract_cards(html, final_url), None
    except (FetchBlocked, FetchFailed) as exc:
        return url, None, str(exc)


def search_links(roles: list[str], location: str, sites: list[str]) -> list[SearchLink]:
    """'Search more' links: a web search restricted to each job site."""
    links = []
    for role in roles[:3]:
        for site in sites[:3]:
            query = quote_plus(f"{role} jobs {location} site:{site}")
            links.append(SearchLink(role=role, site=site, url=f"https://www.google.com/search?q={query}"))
    return links


def run_search(
    resume_text: str,
    location: str,
    llm: LLM,
    fetcher: PoliteFetcher,
    progress: Callable[[str], None],
    index: JSearchClient | None = None,
) -> JobSearchResult:
    progress("Reading your resume and choosing job titles and job sites…")
    plan = llm.plan_search(resume_text, location)
    sites = [s.removeprefix("www.") for s in plan.job_sites]
    progress(f"Looking for {' and '.join(plan.roles[:2])} jobs in {plan.location_label} on {', '.join(sites[:4])}")

    discovery = llm.discover(plan, progress)
    pages = _interleave_by_site(
        [u for u, _ in discovery.results if _on_planned_site(u, sites) and not is_posting_url(u)]
    )[:MAX_PAGES_TO_TRY]
    leads = [(u, t) for u, t in discovery.results if is_posting_url(u)][:MAX_LEADS]
    progress(f"Found {len(pages)} job lists and {len(leads)} single postings. Reading the lists…")

    pages_read: list[str] = []
    skipped = 0
    cards: dict[str, tuple[str, str]] = {}  # url -> (title, text)
    sources: dict[str, str] = {}  # url -> where it was found, when not obvious from the address
    with ThreadPoolExecutor(max_workers=MAX_PAGES_TO_TRY) as pool:
        for url, page_cards, error in pool.map(lambda u: _read_page(fetcher, u), pages):
            if page_cards is None or len(page_cards) < MIN_CARDS_PER_PAGE or len(pages_read) >= MAX_PAGES_TO_READ:
                skipped += page_cards is None
                if error:
                    log_event("page_skipped", url=url, reason=error)
                continue
            pages_read.append(url)
            for card in page_cards:
                cards.setdefault(card.url, (card.title, card.text))
    for url, title in leads:
        cards.setdefault(url.split("?")[0], (title, f"{title} (found in web search results)"))

    from_index = 0
    if index and index.available and len(cards) < ENOUGH_FROM_BOARDS:
        progress(f"Job boards gave {len(cards)} jobs. Adding more from Google's job index…")
        for role in plan.roles[:2]:
            for job in index.search(role, plan.location_label, plan.country_code):
                text = " | ".join(v for v in (job["title"], job["company"], job["location"], job["posted"]) if v)
                if job["url"] not in cards:
                    cards[job["url"]] = (job["title"], f"{text}\n{job['description']}")
                    sources[job["url"]] = job["source"]
                    from_index += 1

    if not cards:
        progress("No job lists could be read for this search.")
        return JobSearchResult(
            location_label=plan.location_label, plan=plan, jobs=[], pages_read=pages_read,
            pages_skipped=skipped, search_links=search_links(plan.roles, plan.location_label, sites),
            index_results=from_index,
        )

    selected = list(cards.items())[:MAX_JOBS]
    progress(f"Scoring {len(selected)} jobs against your resume…")
    ranked = llm.rank_cards(
        resume_text, [(url, f"{title}\n{text}") for url, (title, text) in selected], plan.location_label
    )
    by_url = {r.card_id: r for r in ranked}
    jobs = [
        FoundJob(
            url=url, site=sources.get(url, site_of(url)), title=r.title or title, company=r.company, location=r.location,
            posted=r.posted, fit_score=r.fit_score, verdict=r.verdict, reason=r.reason,
            deal_breakers=r.deal_breakers, summary=text,
        )
        for url, (title, text) in selected
        if (r := by_url.get(url)) and (r.age_days is None or r.age_days <= MAX_AGE_DAYS)
    ]
    jobs.sort(key=lambda j: j.fit_score, reverse=True)
    log_event("smart_search", location=plan.location_label, pages_read=len(pages_read), skipped=skipped,
              from_index=from_index, jobs=len(jobs))
    return JobSearchResult(
        location_label=plan.location_label, plan=plan, jobs=jobs, pages_read=pages_read,
        pages_skipped=skipped, search_links=search_links(plan.roles, plan.location_label, sites),
        index_results=from_index,
    )
