"""Join the same fixture across operators.

A match is accepted only when both team names agree after normalisation (or are close
enough by token similarity) AND the kick-off times are within 30 minutes. Anything that
matches on one team only, or on the names but a different kick-off, is left unmatched and
listed in the quarantine so a human can extend the alias table. A wrong join would blend
two different games into one probability, which is the worst silent error this system
can make.
"""
from __future__ import annotations

import difflib
import re
from datetime import datetime
from itertools import groupby

from .common import Observation

# Words that carry no identity: club-form suffixes and articles. Gender and age markers
# are NOT dropped: "Anderlecht W" is a different team from "RSC Anderlecht" and the two
# can kick off in the same hour. They are folded to one spelling instead (below).
_DROP = {"fc", "cf", "sc", "ac", "afc", "bk", "if", "fk", "sk", "club", "de", "the", "cd", "ca",
         "ud", "sd", "rc", "ss", "us", "as", "ks", "nk", "kf", "fv", "sv", "tsv", "vfb", "vfl",
         "rsc", "krc", "sa", "sp", "spa", "cfc", "ii", "b", "reserves", "res"}
_FOLD = {"w": "women", "women": "women", "ladies": "women", "female": "women", "fem": "women",
         "u21": "u21", "u19": "u19", "u23": "u23", "u20": "u20", "u18": "u18", "u17": "u17"}
# Hand-kept aliases: normalised form -> canonical. Extend from the quarantine list.
ALIASES = {
    "man utd": "manchester united", "man united": "manchester united", "manchester utd": "manchester united",
    "man city": "manchester city", "spurs": "tottenham hotspur", "tottenham": "tottenham hotspur",
    "wolves": "wolverhampton wanderers", "wolverhampton": "wolverhampton wanderers",
    "newcastle": "newcastle united", "nottm forest": "nottingham forest", "forest": "nottingham forest",
    "brighton": "brighton hove albion", "brighton and hove albion": "brighton hove albion",
    "west ham": "west ham united", "leeds": "leeds united", "sheffield utd": "sheffield united",
    "inter": "inter milan", "internazionale": "inter milan", "inter milano": "inter milan",
    "milan": "ac milan", "atletico": "atletico madrid", "atletico de madrid": "atletico madrid",
    "athletic club": "athletic bilbao", "athletic": "athletic bilbao", "real betis": "betis",
    "bayern": "bayern munich", "bayern munchen": "bayern munich", "fc bayern munchen": "bayern munich",
    "borussia mgladbach": "borussia monchengladbach", "gladbach": "borussia monchengladbach",
    "borussia mg": "borussia monchengladbach", "borussia m gladbach": "borussia monchengladbach",
    "borussia m gladbach": "borussia monchengladbach", "psg": "paris saint germain", "paris sg": "paris saint germain",
    "gor mahia": "gor mahia", "afc leopards": "afc leopards", "leopards": "afc leopards",
}


def norm(name: str) -> str:
    s = name.lower()
    s = (s.replace("´", "'").replace("’", "'").replace("ö", "o").replace("ü", "u").replace("ä", "a")
           .replace("é", "e").replace("è", "e").replace("ñ", "n").replace("ç", "c").replace("ø", "o"))
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    toks = [_FOLD.get(t, t) for t in s.split() if t not in _DROP]
    markers = sorted({t for t in toks if t in _FOLD.values()})
    body = " ".join(t for t in toks if t not in _FOLD.values()).strip()
    body = ALIASES.get(body, body)
    return (body + " " + " ".join(markers)).strip()


def _marker(s: str) -> str:
    return " ".join(t for t in s.split() if t in _FOLD.values())


def similar(a: str, b: str, loose: bool = False) -> bool:
    """Same team? Gender/age markers must agree exactly. `loose` is used only when the
    other team of the fixture matched exactly and the kick-off agrees, so weaker name
    evidence suffices: "psv" against "psv eindhoven", "at bilbao" against "athletic bilbao"."""
    if a == b:
        return True
    if not a or not b or _marker(a) != _marker(b):
        return False
    if a in b or b in a:
        return min(len(a), len(b)) >= (3 if loose else 5)
    ta, tb = a.split(), b.split()
    if loose and ta and tb and (ta[0] == tb[0] or ta[-1] == tb[-1]) and len(ta[0]) >= 4:
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= (0.72 if loose else 0.86)


def _kick(o: Observation) -> datetime:
    return datetime.fromisoformat(o.kickoff_utc)


def join(observations: list[Observation]) -> tuple[list[dict], list[dict]]:
    """Group observations into fixtures. Returns (fixtures, quarantine).

    fixture = {home, away, kickoff_utc, country, league, books: {operator: {"1":p,"X":p,"2":p}},
               names: {operator: (home, away)}}
    """
    # First collapse each operator's rows into per-fixture price dicts.
    per_op: dict[str, list[dict]] = {}
    key = lambda o: (o.operator, o.home, o.away, o.kickoff_utc, o.market)
    for k, grp in groupby(sorted(observations, key=key), key=key):
        rows = list(grp)
        prices = {r.outcome: r.price for r in rows}
        labels = {r.outcome: (r.label or r.outcome) for r in rows}
        mkname = next((r.market_name for r in rows if r.market_name), rows[0].market)
        event_url = next((r.event_url for r in rows if r.event_url), "")
        need = ("Over", "Under") if rows[0].market.startswith("O/U") else ("1", "X", "2")
        if not all(x in prices for x in need):
            continue
        r = rows[0]
        per_op.setdefault(r.operator, []).append({
            "operator": r.operator, "home": r.home, "away": r.away, "nh": norm(r.home), "na": norm(r.away),
            "kick": _kick(r), "kickoff_utc": r.kickoff_utc, "country": r.country, "league": r.league,
            "prices": prices, "market": r.market, "labels": labels, "mkname": mkname, "url": event_url,
            "archive": r.archive, "source_url": r.source_url,
        })
    ops = sorted(per_op, key=lambda o: -len(per_op[o]))
    fixtures: list[dict] = []
    quarantine: list[dict] = []
    for op in ops:
        for e in per_op[op]:
            best = None
            for f in fixtures:
                if e["market"] in (f["books"].get(op) or {}):
                    continue          # this operator already matched this market here
                dt = abs((f["kick"] - e["kick"]).total_seconds())
                if dt > 30 * 60:
                    continue
                sh, sa = similar(f["nh"], e["nh"]), similar(f["na"], e["na"])
                if sh and sa:
                    best = f
                    break
                # one team exact, kick-off within the window: accept a looser match on the other
                if (f["nh"] == e["nh"] and similar(f["na"], e["na"], loose=True)) or \
                   (f["na"] == e["na"] and similar(f["nh"], e["nh"], loose=True)):
                    best = f
                    break
                # one team only, or names agree but kick-off does not: worth a human look
                if (sh != sa) and dt <= 30 * 60:
                    quarantine.append({"operator": op, "home": e["home"], "away": e["away"],
                                       "kickoff_utc": e["kickoff_utc"], "near": f["home"] + " v " + f["away"],
                                       "reason": "one team matched"})
            if best is None:
                fixtures.append({"home": e["home"], "away": e["away"], "nh": e["nh"], "na": e["na"], "kick": e["kick"],
                                 "kickoff_utc": e["kickoff_utc"], "country": e["country"], "league": e["league"],
                                 "books": {op: {e["market"]: e["prices"]}}, "names": {op: (e["home"], e["away"])},
                                 "labels": {op: {e["market"]: e["labels"]}}, "mknames": {op: {e["market"]: e["mkname"]}}, "urls": {op: e["url"]},
                                 "archives": {op: e["archive"]}, "sources": {op: e["source_url"]}})
            else:
                best["books"].setdefault(op, {})[e["market"]] = e["prices"]
                best.setdefault("labels", {}).setdefault(op, {})[e["market"]] = e["labels"]
                best.setdefault("mknames", {}).setdefault(op, {})[e["market"]] = e["mkname"]
                best.setdefault("urls", {}).setdefault(op, e["url"])
                best["names"][op] = (e["home"], e["away"])
                best["archives"][op] = e["archive"]
                best["sources"][op] = e["source_url"]
    fixtures.sort(key=lambda f: f["kick"])
    return fixtures, quarantine
