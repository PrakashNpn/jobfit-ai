"""Turn a job-board results page into job "cards" without any AI: each card is the posting link,
its title, and the text shown around it (company, location, salary, summary, date)."""

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

# Paths that look like a single posting on common job boards and career sites.
POSTING_PATH = re.compile(
    r"(/job/\d{4,}|/jobs?/\d{5,}|/jobs/view/|/viewjob|/job-listing|/vacanc(y|ies)/[^/]+|"
    r"/jobs?/[a-z0-9-]*-\d{5,}|/jobs?/[a-z0-9-]+/\d{4,}|/position/|/careers?/[^?#]*\d{4,})",
    re.I,
)
SKIP_TAGS = {"script", "style", "noscript", "svg", "template", "head"}
MAX_CARD_CHARS = 700
MAX_CARDS = 25
SELF_CONTAINED_CHARS = 70


@dataclass
class RawCard:
    url: str
    title: str = ""
    text_parts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        text = re.sub(r"\s+", " ", " ".join(self.text_parts)).strip()
        return text[:MAX_CARD_CHARS]


def is_posting_url(url: str) -> bool:
    return bool(POSTING_PATH.search(urlparse(url).path))


def _canonical(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")


def _same_site(a: str, b: str) -> bool:
    def base(host: str) -> str:
        parts = (host or "").lower().split(".")
        return ".".join(parts[-3:] if len(parts[-1]) == 2 and len(parts) > 2 else parts[-2:])

    return base(urlparse(a).hostname or "") == base(urlparse(b).hostname or "")


class _Tokenizer(HTMLParser):
    """Produces ('text', str) and ('link', url, anchor_text) tokens in page order."""

    def __init__(self, page_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.tokens: list[tuple] = []
        self._skip = 0
        self._href: str | None = None
        self._anchor: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self._skip += 1
        elif tag == "a" and not self._skip:
            href = dict(attrs).get("href")
            self._href = urljoin(self.page_url, href) if href else None
            self._anchor = []

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self._skip:
            self._skip -= 1
        elif tag == "a" and self._href:
            self.tokens.append(("link", self._href, re.sub(r"\s+", " ", "".join(self._anchor)).strip()))
            self._href = None

    def handle_data(self, data):
        if self._skip:
            return
        if self._href is not None:
            self._anchor.append(data)
        if data.strip():
            self.tokens.append(("text", data.strip()))


def extract_cards(html: str, page_url: str) -> list[RawCard]:
    tokenizer = _Tokenizer(page_url)
    tokenizer.feed(html)
    cards: dict[str, RawCard] = {}
    current: RawCard | None = None
    for token in tokenizer.tokens:
        if token[0] == "link":
            _, href, anchor = token
            if is_posting_url(href) and _same_site(href, page_url):
                key = _canonical(href)
                card = cards.get(key)
                if card is None:
                    if len(cards) >= MAX_CARDS:
                        break
                    card = cards[key] = RawCard(url=key)
                if len(anchor) > SELF_CONTAINED_CHARS:
                    # Some boards wrap the whole card in the link: the link text is the card,
                    # and the text that follows belongs to the next job.
                    card.title = card.title or anchor[:150]
                    card.text_parts.append(anchor)
                    current = None
                    continue
                if anchor and len(anchor) > len(card.title):
                    card.title = anchor
                current = card
        elif current is not None:
            current.text_parts.append(token[1])
    return [c for c in cards.values() if len(c.title) >= 4]
