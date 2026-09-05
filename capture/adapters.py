"""One adapter per operator. Each returns a list of Observation for the 1X2 market on
football fixtures kicking off within the capture window, reading only the operator's
public pre-match feed - no login, no session, no page automation.

An adapter that raises is reported as degraded by run.py and its rows are excluded
from that capture; nothing is estimated in its place.
"""
from __future__ import annotations

from datetime import datetime

from .common import (Observation, PoliteClient, archive_raw, eat_to_utc, epoch_ms_to_utc,
                     in_window)

MAX_PAGES = 24          # hard cap per operator per capture, at one request per second


def _num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------- Betika ----------
def betika(client: PoliteClient, stamp: datetime) -> list[Observation]:
    # sub_type_id=1,18: the 1X2 and the TOTAL market arrive together in one request;
    # the totals carry their line as special_bet_value "total=2.5".
    base = ("https://api.betika.com/v1/uo/matches?page={page}&limit=100&tab=upcoming"
            "&sub_type_id=1,18&sport_id=14&sort_id=2&period_id=-2&esports=false")
    out: list[Observation] = []
    for page in range(1, MAX_PAGES + 1):
        url = base.format(page=page)
        try:
            data, text = client.get_json(url, min_interval=2.5)
        except ValueError as e:
            if page == 1 or "''" not in str(e):
                raise                      # a blank FIRST page is still a fault
            # Blank after the client's three quick attempts: on 2026-09-04 this happened
            # on page 5 or 6 every time, and the same page served normally a minute
            # later, so it reads as rate limiting. Rest 45 s and try the page once more;
            # only then keep what was read and stop.
            print(f"Betika     page {page} blank; resting 45 s before one more try", flush=True)
            import time as _t
            _t.sleep(45)
            try:
                data, text = client.get_json(url, min_interval=2.5)
            except ValueError:
                print(f"Betika     page {page} stayed blank; keeping pages 1-{page - 1}", flush=True)
                break
        rows = data.get("data") or []
        if not rows:
            break
        arch = archive_raw("Betika", page, text, stamp)
        beyond = 0
        for m in rows:
            if m.get("is_esport") or m.get("is_srl"):
                continue
            try:
                kick = eat_to_utc(m["start_time"])
            except Exception:
                continue
            if not in_window(kick, stamp):
                beyond += 1
                continue
            common = dict(operator="Betika", sport="Football", country=str(m.get("category") or ""),
                          league=str(m.get("competition_name") or ""), home=str(m["home_team"]),
                          away=str(m["away_team"]), kickoff_utc=kick, market="1X2",
                          source_url=url, observed_at=stamp.isoformat(timespec="seconds"), archive=arch,
                          event_url=f"https://www.betika.com/en-ke/m/{m.get('parent_match_id')}" if m.get("parent_match_id") else "")
            for key, field in (("1", "home_odd"), ("X", "neutral_odd"), ("2", "away_odd")):
                o = Observation(outcome=key, price=_num(m.get(field)), market_name="1X2", label=key, **common)
                if o.valid():
                    out.append(o)
            for blk in m.get("odds") or []:
                if str(blk.get("sub_type_id")) != "18":
                    continue
                for x in blk.get("odds") or []:
                    if "total=2.5" not in str(x.get("special_bet_value") or ""):
                        continue
                    disp = str(x.get("display") or "").upper()
                    key = "Over" if disp.startswith("OVER") else ("Under" if disp.startswith("UNDER") else "")
                    if not key:
                        continue
                    o = Observation(outcome=key, price=_num(x.get("odd_value")), market_name=str(blk.get("name") or "TOTAL"),
                                    label=str(x.get("display") or ""), **dict(common, market="O/U 2.5"))
                    if o.valid():
                        out.append(o)
        # the feed is sorted by start time: once a whole page lies beyond the window, stop
        if len(rows) < 100 or beyond == len(rows):
            break
    return out


# ------------------------------------------------------------- SportyBet ----------
def sportybet(client: PoliteClient, stamp: datetime) -> list[Observation]:
    # timeline=48 restricts the feed to the next 48 hours (1,479 events instead of
    # 2,012 on 2026-09-04); pageSize above 100 is refused, and pages group by
    # tournament so a page holds a little under 100 events.
    # marketId=1,18: 1X2 and every Over/Under line in one request; the 2.5 line is
    # the market whose specifier is "total=2.5".
    base = ("https://www.sportybet.com/api/ke/factsCenter/pcUpcomingEvents?sportId=sr%3Asport%3A1"
            "&marketId=1%2C18&pageSize=100&pageNum={page}&option=1&timeline=48")
    out: list[Observation] = []
    seen_total = None
    got = 0
    for page in range(1, MAX_PAGES + 1):
        url = base.format(page=page)
        data, text = client.get_json(url)
        d = data.get("data") or {}
        tours = d.get("tournaments") or []
        events = [(t, e) for t in tours for e in (t.get("events") or [])]
        if not events:
            break
        seen_total = d.get("totalNum") or seen_total
        got += len(events)
        arch = archive_raw("SportyBet", page, text, stamp)
        for t, e in events:
            try:
                kick = epoch_ms_to_utc(e["estimateStartTime"])
            except Exception:
                continue
            if not in_window(kick, stamp):
                continue
            mk = next((m for m in (e.get("markets") or []) if str(m.get("id")) == "1"), None)
            if not mk:
                continue
            cat = ((e.get("sport") or {}).get("category") or {})
            common = dict(operator="SportyBet", sport="Football", country=str(cat.get("name") or ""),
                          league=str(t.get("name") or ""), home=str(e["homeTeamName"]),
                          away=str(e["awayTeamName"]), kickoff_utc=kick, market="1X2",
                          source_url=url, observed_at=stamp.isoformat(timespec="seconds"), archive=arch,
                          event_url=(f"https://www.sportybet.com/ke/sport/football/{t.get('categoryId')}/{t.get('id')}/{e.get('eventId')}"
                                     if t.get("categoryId") and t.get("id") and e.get("eventId") else ""))
            for oc in mk.get("outcomes") or []:
                key = {"1": "1", "2": "X", "3": "2"}.get(str(oc.get("id")))
                if not key or not oc.get("isActive", 1):
                    continue
                o = Observation(outcome=key, price=_num(oc.get("odds")), market_name=str(mk.get("name") or "1X2"),
                                label=str(oc.get("desc") or key), **common)
                if o.valid():
                    out.append(o)
            ou = next((m for m in (e.get("markets") or []) if str(m.get("id")) == "18"
                       and str(m.get("specifier") or "") == "total=2.5"), None)
            for oc in (ou.get("outcomes") if ou else None) or []:
                desc = str(oc.get("desc") or "").lower()
                key = "Over" if desc.startswith("over") else ("Under" if desc.startswith("under") else "")
                if not key or not oc.get("isActive", 1):
                    continue
                o = Observation(outcome=key, price=_num(oc.get("odds")), market_name=str(ou.get("name") or "Over/Under"),
                                label=str(oc.get("desc") or key), **dict(common, market="O/U 2.5"))
                if o.valid():
                    out.append(o)
        if seen_total and got >= int(seen_total):
            break
    return out


# --------------------------------------------------------------- Odibets ----------
ODIBETS_CORE = ("premier league", "laliga", "la liga", "serie a", "bundesliga", "ligue 1",
                "champions league", "europa", "conference", "championship", "eredivisie",
                "primeira", "kenya", "fkf", "tanzania", "uganda")
ODIBETS_PER_DAY = 32     # requests per day: the biggest competitions plus the core list


def odibets(client: PoliteClient, stamp: datetime) -> list[Observation]:
    """The day feed serves only a first slice (about 30 matches) whatever the limit or
    page, but one request scoped to a competition on a day is complete, and the feed
    lists that day's competitions with match counts. So: per day in the window, read the
    list, then fetch the largest competitions plus the core leagues."""
    from .common import EAT, WINDOW_HOURS
    from datetime import timedelta
    base = "https://odibets.com/pxy2/sportsbook?live=0&sportsbook=sportsbook&resource=sport&sport_id=1"
    out: list[Observation] = []
    seen: set[str] = set()
    local = stamp.astimezone(EAT)
    days = sorted({(local + timedelta(hours=h)).strftime("%Y-%m-%d") for h in range(0, WINDOW_HOURS + 1, 6)})
    page = 0
    for day in days:
        url = f"{base}&day={day}"
        try:
            data, text = client.get_json(url, timeout=90)   # the day list is the slow call
        except Exception as e:
            print(f"Odibets    skipped day {day}: {type(e).__name__}", flush=True)
            continue
        d = data.get("data") or {}
        comps = d.get("competitions") or []
        page += 1
        archive_raw("Odibets", page, text, stamp)
        core = [c for c in comps if any(k in str(c.get("competition_name", "")).lower() for k in ODIBETS_CORE)]
        big = sorted(comps, key=lambda c: -int(c.get("match_count") or 0))
        chosen, ids = [], set()
        for c in core + big:
            cid = str(c.get("competition_id"))
            if cid and cid not in ids and len(chosen) < ODIBETS_PER_DAY:
                ids.add(cid); chosen.append(c)
        for c in chosen:
            url = f"{base}&day={day}&competition_id={c['competition_id']}&limit=100"
            try:
                data, text = client.get_json(url, timeout=60)
            except Exception as e:
                # one slow or failed competition does not take the operator down;
                # its fixtures are simply absent from this capture
                print(f"Odibets    skipped {c.get('competition_name')} on {day}: {type(e).__name__}", flush=True)
                continue
            rows = (data.get("data") or {}).get("matches") or []
            if not rows:
                continue
            page += 1
            arch = archive_raw("Odibets", page, text, stamp)
            _odibets_rows(rows, url, arch, stamp, seen, out)
    return out


def _odibets_rows(rows, url, arch, stamp, seen, out):
    for m in rows:
        pid = str(m.get("parent_match_id") or m.get("game_id") or "")
        if pid in seen:
            continue
        seen.add(pid)
        if True:
            try:
                kick = eat_to_utc(m["start_time"])
            except Exception:
                continue
            if not in_window(kick, stamp):
                continue
            mk = next((x for x in (m.get("markets") or []) if str(x.get("sub_type_id")) == "1"), None)
            if not mk:
                continue
            common = dict(operator="Odibets", sport="Football", country=str(m.get("country_name") or m.get("category_name") or ""),
                          league=str(m.get("competition_name") or ""), home=str(m["home_team"]),
                          away=str(m["away_team"]), kickoff_utc=kick, market="1X2",
                          source_url=url, observed_at=stamp.isoformat(timespec="seconds"), archive=arch,
                          event_url=f"https://odibets.com/sportevent/{m.get('parent_match_id')}" if m.get("parent_match_id") else "")
            for oc in mk.get("outcomes") or []:
                key = str(oc.get("outcome_key") or "")
                if key not in ("1", "X", "2") or not oc.get("active", 1):
                    continue
                o = Observation(outcome=key, price=_num(oc.get("odd_value")), market_name=str(mk.get("odd_type") or "1X2"),
                                label=key, **common)
                if o.valid():
                    out.append(o)


ADAPTERS = {"Betika": betika, "SportyBet": sportybet, "Odibets": odibets}
