import httpx
import pytest

from app.cards import extract_cards, is_posting_url
from app.jsearch import JSearchClient
from app.llm import Discovery
from app.schemas import RankedCard, SearchPlan
from app.smartsearch import ENOUGH_FROM_BOARDS, _interleave_by_site, run_search
from app.webfetch import FetchBlocked, PoliteFetcher, parse_robots, robots_allows

# The relevant part of JobsDB's real robots.txt (Oct 2026).
JOBSDB_ROBOTS = """
User-agent: Mediapartners-Google
User-agent: AdIdxBot
Disallow:

User-agent: *
Disallow: */job/
Disallow: *?
Disallow: /graphql
Allow: *?keywords

User-agent: GPTBot
Disallow: */job/
"""


# ---------- robots.txt ----------

@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ("/full-stack-developer-jobs/in-Bangkok", True),
        ("/job/95320999", False),
        ("/th/job/95320999", False),
        ("/full-stack-jobs?page=2", False),
        ("/jobs?keywords=react", True),  # longer Allow rule wins
        ("/graphql", False),
    ],
)
def test_robots_rules_follow_google_semantics(path, allowed):
    rules = parse_robots(JOBSDB_ROBOTS, "JobFitAI/1.0")
    assert robots_allows(rules, path) is allowed


def test_robots_specific_agent_group_wins():
    rules = parse_robots("User-agent: *\nDisallow: /\n\nUser-agent: JobFitAI\nAllow: /\n", "JobFitAI/1.0 (+https://x)")
    assert robots_allows(rules, "/anything")


def test_robots_end_anchor():
    rules = parse_robots("User-agent: *\nDisallow: /*.pdf$\n")
    assert not robots_allows(rules, "/files/cv.pdf")
    assert robots_allows(rules, "/files/cv.pdf.html")


# ---------- address safety ----------

def test_fetcher_refuses_non_https_and_private_addresses():
    fetcher = PoliteFetcher()
    with pytest.raises(FetchBlocked, match="HTTPS"):
        fetcher.get_html("http://th.jobsdb.com/")
    with pytest.raises(FetchBlocked, match="public"):
        fetcher.get_html("https://127.0.0.1/")


def test_fetcher_respects_robots_before_fetching():
    seen = []

    def handler(request):
        seen.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=JOBSDB_ROBOTS)
        return httpx.Response(200, text="<html>ok</html>")

    fetcher = PoliteFetcher(transport=httpx.MockTransport(handler), check_dns=False)
    with pytest.raises(FetchBlocked, match="robots"):
        fetcher.get_html("https://th.jobsdb.com/job/95320999")
    _, html = fetcher.get_html("https://th.jobsdb.com/full-stack-developer-jobs")
    assert html == "<html>ok</html>"
    assert seen.count("/robots.txt") == 1  # cached
    assert "/job/95320999" not in seen  # blocked page was never requested


# ---------- job cards ----------

SIDE_BY_SIDE = """<html><head><script>var x = "<a href='/job/99999999'>no</a>";</script></head><body>
<nav><a href="/jobs">All jobs</a></nav>
<article><a href="/job/95470451?type=standard">Full-Stack Developer</a>
  <span>Lawcluster Co., Ltd.</span><span>Thon Buri, Bangkok</span><span>Listed 21 hours ago</span></article>
<article><a href="/job/95441143">Full Stack Developer (Golang/React)</a>
  <span>HUMANICA</span><span>Pathum Wan</span><a href="/job/95441143">View</a></article>
<a href="https://other-site.com/job/12345678">Ad elsewhere</a>
</body></html>"""

WRAPPED = """<html><body>
<a href="/th/company/job/1928793"><h3>Python Full Stack Developer (Junior)</h3><p>Admire Construction · Nakhon Ratchasima · 15,000 - 25,000 THB · 24 Oct</p></a>
<p>Next job's text that must not leak</p>
<a href="/th/company/job/1789670"><h3>Full Stack Developer</h3><p>World Med Center · Krabi · 35,000 - 55,000 THB · 24 Oct</p></a>
</body></html>"""


def test_cards_from_links_next_to_their_details():
    cards = extract_cards(SIDE_BY_SIDE, "https://th.jobsdb.com/full-stack-developer-jobs")
    assert [c.url for c in cards] == ["https://th.jobsdb.com/job/95470451", "https://th.jobsdb.com/job/95441143"]
    assert cards[0].title == "Full-Stack Developer"
    assert "Lawcluster" in cards[0].text and "21 hours ago" in cards[0].text
    assert cards[1].title == "Full Stack Developer (Golang/React)"  # longest link text wins over "View"


def test_cards_wrapped_inside_the_link():
    cards = extract_cards(WRAPPED, "https://www.jobthai.com/th/jobs")
    assert len(cards) == 2
    assert "Admire Construction" in cards[0].text
    assert "must not leak" not in cards[0].text


def test_posting_url_detection():
    assert is_posting_url("https://th.jobsdb.com/job/95470451")
    assert is_posting_url("https://www.linkedin.com/jobs/view/4265938387")
    assert not is_posting_url("https://th.jobsdb.com/full-stack-developer-jobs/in-Bangkok")


# ---------- JSearch client ----------

def test_jsearch_maps_postings_and_caches():
    calls = []

    def handler(request):
        calls.append(dict(request.url.params))
        assert request.headers["x-api-key"] == "k"
        return httpx.Response(200, json={"data": [
            {"job_title": "AI Engineer", "employer_name": "Acme", "job_location": "Singapore", "job_posted_at": "2 days ago",
             "job_publisher": "LinkedIn Singapore", "job_apply_link": "https://sg.linkedin.com/jobs/view/1", "job_description": "RAG"},
            {"job_title": "No link"},
        ]})

    client = JSearchClient("k", transport=httpx.MockTransport(handler))
    jobs = client.search("AI Engineer", "Singapore", "sg")
    client.search("AI Engineer", "Singapore", "sg")
    assert len(calls) == 1 and calls[0]["query"] == "AI Engineer in Singapore" and calls[0]["country"] == "sg"
    assert jobs == [{"url": "https://sg.linkedin.com/jobs/view/1", "title": "AI Engineer", "company": "Acme",
                     "location": "Singapore", "posted": "2 days ago", "source": "LinkedIn Singapore", "description": "RAG"}]


def test_jsearch_failure_means_no_results_not_an_error():
    client = JSearchClient("k", transport=httpx.MockTransport(lambda r: httpx.Response(429)))
    assert client.search("AI Engineer", "Singapore", "sg") == []


# ---------- the pipeline's decisions ----------

def test_interleave_takes_pages_from_different_sites_in_turn():
    urls = ["https://a.com/1", "https://a.com/2", "https://b.com/1", "https://a.com/3", "https://c.com/1"]
    assert _interleave_by_site(urls) == ["https://a.com/1", "https://b.com/1", "https://c.com/1", "https://a.com/2", "https://a.com/3"]


class FakeLLM:
    def __init__(self, ages=None):
        self.ages = ages or {}
        self.ranked = []

    def plan_search(self, resume_text, location):
        return SearchPlan(roles=["AI Engineer"], seniority="mid-level", location_label="Singapore",
                          country_code="sg", job_sites=["sg.jobstreet.com", "linkedin.com"])

    def discover(self, plan, on_progress):
        return Discovery(results=[("https://sg.jobstreet.com/ai-engineer-jobs", "AI Engineer jobs")])

    def rank_cards(self, resume_text, cards, location_label):
        self.ranked = cards
        return [RankedCard(card_id=cid, title="t", company=None, location=None, posted=None,
                           age_days=self.ages.get(cid), fit_score=60, verdict="possible", reason="r", deal_breakers=[])
                for cid, _ in cards]


class BlockedFetcher:
    def get_html(self, url, respect_robots=True):
        raise FetchBlocked("blocked")


class FakeIndex:
    available = True

    def __init__(self):
        self.calls = 0

    def search(self, role, location_label, country_code):
        self.calls += 1
        return [{"url": "https://sg.linkedin.com/jobs/view/1", "title": "AI Engineer", "company": "Acme",
                 "location": "Singapore", "posted": "2 days ago", "source": "LinkedIn Singapore", "description": "RAG"}]


def test_index_fills_in_when_job_boards_block_us():
    index = FakeIndex()
    result = run_search("resume", "Singapore", FakeLLM(), BlockedFetcher(), lambda m: None, index)
    assert index.calls == 1
    assert result.pages_skipped == 1 and result.index_results == 1
    assert result.jobs[0].site == "LinkedIn Singapore"


def test_index_not_used_when_boards_give_enough():
    html = "".join(f'<a href="/job/9500{n:04d}">Job {n}</a><span>Company {n}</span>' for n in range(ENOUGH_FROM_BOARDS))

    class Fetcher:
        def get_html(self, url, respect_robots=True):
            return url, html

    index = FakeIndex()
    result = run_search("resume", "Singapore", FakeLLM(), Fetcher(), lambda m: None, index)
    assert index.calls == 0
    assert len(result.jobs) == ENOUGH_FROM_BOARDS


def test_old_postings_are_dropped():
    llm = FakeLLM(ages={"https://sg.linkedin.com/jobs/view/1": 400})
    result = run_search("resume", "Singapore", llm, BlockedFetcher(), lambda m: None, FakeIndex())
    assert result.jobs == []
