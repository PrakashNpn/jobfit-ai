"""JSearch (Google for Jobs data via OpenWeb Ninja): a second source for the smart search, used for
locations whose big job boards block automated reading. It has no Thailand data, so it's only
called when the job-board pages didn't give enough jobs."""

import time

import httpx

from .observability import log_event

URL = "https://api.openwebninja.com/jsearch/search"
TIMEOUT_SECONDS = 25
CACHE_SECONDS = 24 * 3600


class JSearchClient:
    def __init__(self, api_key: str | None, transport: httpx.BaseTransport | None = None) -> None:
        self.api_key = api_key
        self.transport = transport
        self._cache: dict[tuple, tuple[float, list[dict]]] = {}

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def search(self, role: str, location_label: str, country_code: str | None) -> list[dict]:
        """Return postings as dicts: url, title, company, location, posted, source, description."""
        remote = country_code is None
        query = f"remote {role}" if remote else f"{role} in {location_label}"
        key = (query, country_code)
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < CACHE_SECONDS:
            return hit[1]
        params = {"query": query, "page": 1, "num_pages": 1, "date_posted": "month", "country": (country_code or "us").lower()}
        started = time.perf_counter()
        try:
            with httpx.Client(transport=self.transport, timeout=TIMEOUT_SECONDS) as client:
                res = client.get(URL, params=params, headers={"x-api-key": self.api_key or ""})
        except httpx.HTTPError:
            log_event("jsearch_failed", reason="network")
            return []
        log_event("jsearch_call", status=res.status_code, latency_ms=round((time.perf_counter() - started) * 1000))
        if res.status_code != 200:
            return []  # a second source: if it's down or out of quota, the search just uses the job boards
        jobs = []
        for j in res.json().get("data") or []:
            url = j.get("job_apply_link") or j.get("job_google_link")
            if not (j.get("job_title") and url):
                continue
            jobs.append(
                {
                    "url": url,
                    "title": j["job_title"],
                    "company": j.get("employer_name"),
                    "location": j.get("job_location") or j.get("job_country"),
                    "posted": j.get("job_posted_at"),
                    "source": j.get("job_publisher") or "Google for Jobs",
                    "description": (j.get("job_description") or "")[:2500],
                }
            )
        self._cache[key] = (time.time(), jobs)
        return jobs
