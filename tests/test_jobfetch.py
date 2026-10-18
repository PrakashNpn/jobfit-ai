from pathlib import Path

import httpx
import pytest

from app.jobfetch import (
    JobFetchError,
    JobsDBFetcher,
    UnsupportedJobUrl,
    canonical_job_url,
    parse_job_page,
)

FIXTURE = (Path(__file__).parent / "fixtures" / "jobsdb_job.html").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("pasted", "expected"),
    [
        ("https://th.jobsdb.com/job/95333770/apply?sol=abc123", "https://th.jobsdb.com/job/95333770"),
        ("th.jobsdb.com/job/95320999", "https://th.jobsdb.com/job/95320999"),
        ("https://th.jobsdb.com/th/job/95320999?ref=search", "https://th.jobsdb.com/job/95320999"),
        ("http://hk.jobsdb.com/job/12345678", "https://hk.jobsdb.com/job/12345678"),
        ("  https://www.jobsdb.com/job/12345678  ", "https://jobsdb.com/job/12345678"),
    ],
)
def test_canonical_job_url(pasted, expected):
    assert canonical_job_url(pasted) == expected


@pytest.mark.parametrize(
    "pasted",
    [
        "https://www.linkedin.com/jobs/view/123456",
        "https://jobsdb.com.evil.example/job/12345678",
        "https://evil-jobsdb.com/job/12345678",
        "https://th.jobsdb.com/jobs/in-Bangkok",
        "ftp://th.jobsdb.com/job/12345678",
        "http://127.0.0.1/job/12345678",
    ],
)
def test_rejects_other_links(pasted):
    with pytest.raises(UnsupportedJobUrl):
        canonical_job_url(pasted)


def test_parse_job_page():
    job = parse_job_page(FIXTURE, "https://th.jobsdb.com/job/1")
    assert job.title == "Frontend Developer (React)"  # first title only, not the footer one
    assert job.company == "Example Studio Co., Ltd."
    assert job.location == "Sathon, Bangkok"
    assert job.work_type == "Full time"
    assert job.salary == "฿40,000 – ฿55,000 per month"
    assert "- 3+ years with React and TypeScript" in job.description
    assert "- Bonus: experience with AI agents" in job.description  # <li><p>...</p></li>
    assert "Hybrid: 2 days in the office\nApply by 30 November" in job.description
    assert "Home" not in job.description


def test_as_text_includes_key_facts():
    text = parse_job_page(FIXTURE, "u").as_text()
    assert text.startswith("Frontend Developer (React)\nExample Studio Co., Ltd.\n")
    assert "Sathon, Bangkok · Full time · ฿40,000" in text


def test_expired_job():
    with pytest.raises(JobFetchError, match="no longer advertised"):
        parse_job_page("<html><p>This job is no longer advertised</p></html>", "u")


def test_page_without_description():
    with pytest.raises(JobFetchError, match="couldn't find"):
        parse_job_page("<html><h1>Something else</h1></html>", "u")


def _fetcher(handler) -> JobsDBFetcher:
    return JobsDBFetcher(transport=httpx.MockTransport(handler))


def test_fetch_requests_the_canonical_url():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, text=FIXTURE)

    job = _fetcher(handler).fetch("https://th.jobsdb.com/job/95333770/apply?sol=abc")
    assert seen == ["https://th.jobsdb.com/job/95333770"]
    assert job.title == "Frontend Developer (React)"


def test_fetch_refuses_redirect_off_jobsdb():
    def handler(request):
        if request.url.host == "th.jobsdb.com":
            return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data"})
        raise AssertionError("must not request a non-JobsDB host")

    with pytest.raises(JobFetchError, match="redirected"):
        _fetcher(handler).fetch("https://th.jobsdb.com/job/12345678")


def test_fetch_not_found():
    with pytest.raises(JobFetchError, match="doesn't exist"):
        _fetcher(lambda r: httpx.Response(404)).fetch("https://th.jobsdb.com/job/12345678")


def test_fetch_rejects_huge_pages():
    with pytest.raises(JobFetchError, match="large"):
        _fetcher(lambda r: httpx.Response(200, content=b"x" * (4 * 1024 * 1024))).fetch(
            "https://th.jobsdb.com/job/12345678"
        )
