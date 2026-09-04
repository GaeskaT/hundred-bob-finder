"""Shared pieces of the capture pipeline: the evidence-carrying observation, a polite
HTTP client (identified user agent, one request per second per host, robots honoured),
and the raw-response archive.

Every observation carries the five fields the Hundred Bob Standard requires: what was
observed, the source URL, the capture timestamp, a pointer to the archived raw response,
and the collector. Anything missing one of them is dropped, never estimated.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

USER_AGENT = ("HundredBobFinder/0.1 (+https://github.com/GaeskaT/hundred-bob-finder; "
              "odds comparison for consumers; one request per second; contact via the repo)")
COLLECTOR = "hundred-bob-finder capture v0.1"
EAT = timezone(timedelta(hours=3))          # Africa/Nairobi, no DST
MIN_INTERVAL_S = 1.0                         # per host
WINDOW_HOURS = 48                            # only fixtures kicking off within this window
REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
RAW = DATA / "raw"


@dataclass
class Observation:
    operator: str          # display name, e.g. "Betika"
    sport: str             # "Football"
    country: str           # "England"
    league: str            # "Premier League"
    home: str
    away: str
    kickoff_utc: str       # ISO 8601, UTC
    market: str            # "1X2"
    outcome: str           # "1" | "X" | "2"
    price: float
    source_url: str
    observed_at: str       # ISO 8601, UTC
    archive: str           # relative path of the archived raw response
    collector: str = COLLECTOR

    def valid(self) -> bool:
        return all([self.operator, self.home, self.away, self.kickoff_utc, self.market,
                    self.outcome, self.price and self.price > 1.0, self.source_url,
                    self.observed_at, self.archive, self.collector])


class PoliteClient:
    """GET JSON with an identified user agent, at most one request per second per host,
    and only where robots.txt allows this user agent. Raises on refusal so an adapter
    reports itself as degraded instead of quietly returning nothing."""

    def __init__(self):
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _allowed(self, url: str) -> bool:
        host = urllib.parse.urlsplit(url).netloc
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                req = urllib.request.Request(f"https://{host}/robots.txt", headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=20) as r:
                    rp.parse(r.read().decode("utf-8", "replace").splitlines())
                self._robots[host] = rp
            except urllib.error.HTTPError as e:
                if e.code in (404, 410):
                    # No robots file at all is, by the standard, no restriction
                    # (api.betika.com answers 404 with a JSON "unknown route").
                    rp.parse([])
                    self._robots[host] = rp
                else:
                    # 401/403 or a bot challenge: the host is refusing, so we do too.
                    self._robots[host] = None
                    self.robots_note[host] = f"robots.txt answered HTTP {e.code}"
            except Exception as e:
                self._robots[host] = None
                self.robots_note[host] = f"robots.txt unreachable: {type(e).__name__}"
        rp = self._robots[host]
        ok = bool(rp) and rp.can_fetch(USER_AGENT, url)
        if rp and not ok:
            self.robots_note[host] = "robots.txt disallows this path for this user agent"
        return ok

    robots_note: dict[str, str] = {}

    def get_json(self, url: str, timeout: int = 30):
        if not self._allowed(url):
            host = urllib.parse.urlsplit(url).netloc
            raise PermissionError(f"{self.robots_note.get(host, 'robots.txt refused')} ({host}); "
                                  f"a host that refuses robots is not captured")
        host = urllib.parse.urlsplit(url).netloc
        wait = MIN_INTERVAL_S - (time.monotonic() - self._last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                   "Accept": "application/json, text/plain, */*"})
        text = ""
        for attempt, pause in ((1, 3), (2, 8), (3, 0)):
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
            self._last[host] = time.monotonic()
            text = body.decode("utf-8", "replace").strip()
            if text and text[0] in "{[":
                return json.loads(text), text
            # Betika intermittently answers a page with an empty body (page 1 once,
            # page 5 once on 2026-09-04) and serves the same page normally a minute
            # later. Three attempts with a short backoff; then the caller decides.
            if pause:
                time.sleep(pause)
        raise ValueError(f"not JSON from {url}: {text[:80]!r}")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def archive_raw(operator: str, page: int, text: str, stamp: datetime) -> str:
    """Keep the raw response beside the board. One file per operator per page per
    capture; the workflow prunes to the latest capture so the repo stays small."""
    RAW.mkdir(parents=True, exist_ok=True)
    name = f"{operator.lower()}-{stamp.strftime('%Y%m%dT%H%M%SZ')}-p{page}.json"
    (RAW / name).write_text(text, encoding="utf-8")
    return f"data/raw/{name}"


def eat_to_utc(s: str) -> str:
    """'2026-09-04 21:45:00' in Nairobi time -> ISO UTC."""
    dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=EAT)
    return dt.astimezone(timezone.utc).isoformat(timespec="minutes")


def epoch_ms_to_utc(ms: int) -> str:
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat(timespec="minutes")


def in_window(kickoff_utc: str, stamp: datetime) -> bool:
    k = datetime.fromisoformat(kickoff_utc)
    return stamp - timedelta(minutes=5) <= k <= stamp + timedelta(hours=WINDOW_HOURS)


def to_dict(o: Observation) -> dict:
    return asdict(o)
