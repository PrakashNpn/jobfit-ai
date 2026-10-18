"""Read a single JobsDB job page from a link the user pasted.

Safety rules: only JobsDB job links are accepted, the URL we request is rebuilt from the
job ID (so users can't point the server at arbitrary addresses), every request in a
redirect chain must stay on JobsDB, and responses are capped in time and size.
"""

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

ALLOWED_HOST = re.compile(r"^([a-z]{2}\.)?jobsdb\.com$")
JOB_ID = re.compile(r"/job/(\d{5,12})(?:[/?#]|$)")
TIMEOUT_SECONDS = 10
MAX_BYTES = 3 * 1024 * 1024
USER_AGENT = "Mozilla/5.0 (compatible; JobFitAI/0.2; reads one job page on user request)"

# JobsDB marks the parts of a job page with data-automation attributes.
FIELDS = {
    "job-detail-title": "title",
    "advertiser-name": "company",
    "job-detail-location": "location",
    "job-detail-work-type": "work_type",
    "job-detail-salary": "salary",
    "jobAdDetails": "description",
}
BLOCK_TAGS = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr"}
VOID_TAGS = {"br", "img", "hr", "input", "meta", "link", "source", "wbr"}


class UnsupportedJobUrl(ValueError):
    pass


class JobFetchError(RuntimeError):
    pass


@dataclass
class FetchedJob:
    url: str
    title: str
    company: str | None
    location: str | None
    work_type: str | None
    salary: str | None
    description: str

    def as_text(self) -> str:
        """The job as plain text, ready for the fit analysis."""
        meta = " · ".join(v for v in (self.location, self.work_type, self.salary) if v)
        header = "\n".join(v for v in (self.title, self.company, meta) if v)
        return f"{header}\n\n{self.description}".strip()


def canonical_job_url(raw: str) -> str:
    """Validate a pasted link and rebuild it as https://<host>/job/<id>."""
    raw = raw.strip()
    if "://" not in raw:
        raw = "https://" + raw  # people often paste "th.jobsdb.com/job/..." without the scheme
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if parsed.scheme not in ("http", "https") or not ALLOWED_HOST.match(host):
        raise UnsupportedJobUrl(
            "We can read JobsDB links. For other sites, please paste the job description."
        )
    match = JOB_ID.search(parsed.path)
    if not match:
        raise UnsupportedJobUrl("That JobsDB link doesn't point to a job post.")
    return f"https://{host}/job/{match.group(1)}"


class _JobPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.fields: dict[str, list[str]] = {}
        self._stack: list[str | None] = []  # field name (or None) for each open element

    @property
    def _current(self) -> str | None:
        return next((f for f in reversed(self._stack) if f), None)

    def handle_starttag(self, tag, attrs):
        field = FIELDS.get(dict(attrs).get("data-automation") or "")
        if field and field in self.fields:
            field = None  # keep the first occurrence only
        if field:
            self.fields[field] = []
        current = field or self._current
        if current == "description" and tag in BLOCK_TAGS:
            self.fields[current].append("\n- " if tag == "li" else "\n")
        if tag not in VOID_TAGS:
            self._stack.append(field)

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if self._stack:
            self._stack.pop()

    def handle_data(self, data):
        if self._current:
            self.fields[self._current].append(data)


def _clean(parts: list[str] | None) -> str | None:
    if not parts:
        return None
    text = "".join(parts).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"^-\n+(?=\S)", "- ", text, flags=re.M)  # bullet whose text sat in a nested <p>
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text or None


def parse_job_page(html: str, url: str) -> FetchedJob:
    parser = _JobPageParser()
    parser.feed(html)
    fields = {name: _clean(parts) for name, parts in parser.fields.items()}
    if not fields.get("description"):
        if "no longer advertised" in html.lower():
            raise JobFetchError("This job is no longer advertised on JobsDB.")
        raise JobFetchError("We couldn't find a job description on that page. Please paste the text instead.")
    return FetchedJob(
        url=url,
        title=fields.get("title") or "Job posting",
        company=fields.get("company"),
        location=fields.get("location"),
        work_type=fields.get("work_type"),
        salary=fields.get("salary"),
        description=fields["description"],
    )


def _stay_on_jobsdb(request: httpx.Request) -> None:
    if not ALLOWED_HOST.match(request.url.host.removeprefix("www.")) or request.url.scheme != "https":
        raise JobFetchError("JobsDB redirected somewhere we can't follow.")


class JobsDBFetcher:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport  # tests pass a mock transport; None means the real network

    def fetch(self, raw_url: str) -> FetchedJob:
        url = canonical_job_url(raw_url)
        try:
            with httpx.Client(
                transport=self._transport,
                timeout=TIMEOUT_SECONDS,
                follow_redirects=True,
                max_redirects=3,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "en,th;q=0.8"},
                event_hooks={"request": [_stay_on_jobsdb]},
            ) as client, client.stream("GET", url) as response:
                if response.status_code == 404:
                    raise JobFetchError("JobsDB says this job doesn't exist. Check the link.")
                if response.status_code != 200:
                    raise JobFetchError(f"JobsDB didn't return the page (status {response.status_code}). Please paste the text instead.")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise JobFetchError("That page is unexpectedly large. Please paste the text instead.")
                html = body.decode(response.encoding or "utf-8", errors="replace")
        except httpx.HTTPError as exc:
            raise JobFetchError("We couldn't reach JobsDB. Please try again or paste the text instead.") from exc
        return parse_job_page(html, url)
