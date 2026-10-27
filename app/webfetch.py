"""Polite, safe reading of public web pages for job search.

- robots.txt is checked before every automated request (wildcard-aware, Google's rules).
- Only public HTTPS addresses are fetched: hosts that resolve to private, loopback or
  link-local addresses are refused, on every redirect hop.
- Responses are capped in time and size.
"""

import ipaddress
import re
import socket
import time
from urllib.parse import urlparse

import httpx

USER_AGENT = "JobFitAI/1.0 (+https://github.com/PrakashNpn/jobfit-ai; reads public job listing pages on user request)"
TIMEOUT_SECONDS = 10
MAX_BYTES = 4 * 1024 * 1024
ROBOTS_CACHE_SECONDS = 6 * 3600


class FetchBlocked(RuntimeError):
    """The page may not be fetched (robots.txt, unsafe address, or not HTTPS)."""


class FetchFailed(RuntimeError):
    pass


# ---------- robots.txt ----------

def _rule_regex(path: str) -> re.Pattern:
    # Google semantics: '*' matches anything, a trailing '$' anchors the end.
    anchored = path.endswith("$")
    body = re.escape(path[:-1] if anchored else path).replace(r"\*", ".*")
    return re.compile(body + ("$" if anchored else ""))


def parse_robots(text: str, agent: str = "*") -> list[tuple[bool, str]]:
    """Return (allow, path) rules for the group that applies to `agent` (falls back to '*')."""
    groups: list[tuple[list[str], list[tuple[bool, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[bool, str]] = []
    in_rules = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        field, value = (part.strip() for part in line.split(":", 1))
        field = field.lower()
        if field == "user-agent":
            if in_rules:
                groups.append((agents, rules))
                agents, rules, in_rules = [], [], False
            agents.append(value.lower())
        elif field in ("allow", "disallow"):
            in_rules = True
            if value:
                rules.append((field == "allow", value))
    if agents:
        groups.append((agents, rules))

    agent = agent.lower()
    specific = [r for a, r in groups if any(x != "*" and x in agent for x in a)]
    if specific:
        return [rule for group in specific for rule in group]
    return [rule for a, r in groups if "*" in a for rule in r]


def robots_allows(rules: list[tuple[bool, str]], path_and_query: str) -> bool:
    """Longest matching rule wins; on a tie, Allow wins. No matching rule means allowed."""
    best: tuple[int, bool] | None = None
    for allow, path in rules:
        if _rule_regex(path).match(path_and_query):
            candidate = (len(path), allow)
            if best is None or candidate[0] > best[0] or (candidate[0] == best[0] and allow):
                best = candidate
    return True if best is None else best[1]


# ---------- Address safety ----------

def _is_public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False
    return bool(infos) and all(ipaddress.ip_address(info[4][0]).is_global for info in infos)


class PoliteFetcher:
    def __init__(self, transport: httpx.BaseTransport | None = None, check_dns: bool = True) -> None:
        self.transport = transport
        self.check_dns = check_dns  # tests with a mock transport skip DNS
        self._robots: dict[str, tuple[float, list[tuple[bool, str]]]] = {}

    def _check_url(self, url: httpx.URL | str) -> None:
        url = httpx.URL(str(url))
        if url.scheme != "https":
            raise FetchBlocked("Only HTTPS pages are read.")
        if self.check_dns and not _is_public_host(url.host):
            raise FetchBlocked("That address isn't a public website.")

    def _client(self) -> httpx.Client:
        return httpx.Client(
            transport=self.transport,
            timeout=TIMEOUT_SECONDS,
            follow_redirects=True,
            max_redirects=3,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en,th;q=0.8"},
            event_hooks={"request": [lambda request: self._check_url(request.url)]},
        )

    def robots_rules(self, host: str) -> list[tuple[bool, str]]:
        cached = self._robots.get(host)
        if cached and time.time() - cached[0] < ROBOTS_CACHE_SECONDS:
            return cached[1]
        try:
            with self._client() as client:
                res = client.get(f"https://{host}/robots.txt")
            # No robots.txt means no restrictions; an error page means "don't know", so be careful.
            rules = parse_robots(res.text, USER_AGENT) if res.status_code == 200 else []
            if res.status_code >= 500:
                rules = [(False, "/")]
        except (httpx.HTTPError, FetchBlocked):
            rules = [(False, "/")]
        self._robots[host] = (time.time(), rules)
        return rules

    def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        return robots_allows(self.robots_rules(parsed.hostname or ""), path)

    def get_html(self, url: str, respect_robots: bool = True) -> tuple[str, str]:
        """Return (final_url, html). Raises FetchBlocked or FetchFailed."""
        self._check_url(url)
        if respect_robots and not self.allowed(url):
            raise FetchBlocked("The site's robots.txt doesn't allow automated reading of this page.")
        try:
            with self._client() as client, client.stream("GET", url) as res:
                if res.status_code != 200:
                    raise FetchFailed(f"The page returned status {res.status_code}.")
                body = bytearray()
                for chunk in res.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise FetchFailed("The page is too large.")
                return str(res.url), body.decode(res.encoding or "utf-8", errors="replace")
        except httpx.HTTPError as exc:
            raise FetchFailed("The page couldn't be loaded.") from exc
