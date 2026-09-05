"""Run one capture: every adapter, the join, and the board the page loads.

    python -m capture.run            # writes data/board.json, data/observations.csv,
                                     # data/quarantine.json, data/raw/*.json, data/status.json

Exit code is 0 even when an operator is degraded - the board says so - and 1 only when
fewer than three operators produced rows, because a consensus needs three.
"""
from __future__ import annotations

import csv
import json
import sys
import traceback

from .adapters import ADAPTERS
from .common import DATA, RAW, EAT, PoliteClient, now_utc, to_dict
from .match import join

MIN_BOOKS_FOR_CONSENSUS = 3
MAX_FIXTURES = 400      # the page's table stays usable; the CSV keeps everything


def main() -> int:
    stamp = now_utc()
    client = PoliteClient()
    DATA.mkdir(parents=True, exist_ok=True)
    # prune the previous capture's raw files; the board keeps the current pointers
    if RAW.exists():
        for p in RAW.glob("*.json"):
            p.unlink()
    observations, status = [], {}
    for name, fn in ADAPTERS.items():
        try:
            rows = fn(client, stamp)
            fixtures_n = len({(r.home, r.away, r.kickoff_utc) for r in rows})
            status[name] = {"ok": True, "observations": len(rows), "fixtures": fixtures_n}
            observations += rows
            print(f"{name:<10} {len(rows):>5} prices on {fixtures_n:>4} fixtures", flush=True)
        except Exception as e:  # degraded, reported, excluded
            status[name] = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:160]}"}
            print(f"{name:<10} DEGRADED {type(e).__name__}: {str(e)[:120]}", flush=True)
            traceback.print_exc(limit=1)

    fixtures, quarantine = join(observations)
    operators = [n for n, s in status.items() if s.get("ok")]
    with_consensus = [f for f in fixtures if sum(1 for b in f["books"].values() if "1X2" in b) >= MIN_BOOKS_FOR_CONSENSUS]
    print(f"joined: {len(fixtures)} fixtures, {len(with_consensus)} priced by >= {MIN_BOOKS_FOR_CONSENSUS} operators, "
          f"{len(quarantine)} in quarantine")

    # ---- the board the page loads (same shape as the page's illustrative BOARD) ------
    board_fixtures = []
    MARKETS = {"1X2": (["Home win", "Draw", "Away win"], ["1", "X", "2"]),
               "O/U 2.5": (["Over 2.5", "Under 2.5"], ["Over", "Under"])}
    for f in sorted(fixtures, key=lambda f: (-len(f["books"]), f["kick"]))[:MAX_FIXTURES]:
        local = f["kick"].astimezone(EAT)
        present = {mk for b in f["books"].values() for mk in b}
        for mk in [m for m in MARKETS if m in present]:
            labels, keys = MARKETS[mk]
            board_fixtures.append({
                "fx": f"{f['home']} v {f['away']} · {local.strftime('%a %H:%M')}",
                "home": f["home"], "away": f["away"], "kickoff_utc": f["kickoff_utc"],
                "sport": "Football", "league": f["league"], "country": f["country"], "mk": mk,
                "out": labels, "keys": keys,
                "labels": {op: (f.get("labels", {}).get(op) or {}).get(mk) for op in operators
                           if mk in (f["books"].get(op) or {})},
                "mknames": {op: (f.get("mknames", {}).get(op) or {}).get(mk) for op in operators
                            if mk in (f["books"].get(op) or {})},
                "odds": [[f["books"][op][mk][k] for k in keys] if mk in (f["books"].get(op) or {}) else None
                         for op in operators],
                "names": {op: f["names"][op] for op in f["names"]},
                "archives": {op: f["archives"][op] for op in f["archives"]},
            })
    board_fixtures.sort(key=lambda b: b["kickoff_utc"])
    board = {
        "captured_at": stamp.isoformat(timespec="seconds"),
        "captured_at_eat": stamp.astimezone(EAT).strftime("%a %d %b %H:%M"),
        "operators": operators,
        "status": status,
        "window_hours": 48,
        "fixtures": board_fixtures,
        "counts": {"observations": len(observations), "fixtures": len(fixtures),
                   "markets": sorted({e["mk"] for e in board_fixtures}),
                   "with_consensus": len(with_consensus), "quarantine": len(quarantine)},
        "collector": "hundred-bob-finder capture v0.1",
        "licence": "CC BY 4.0 for the observations; prices are the operators' public offers at capture time",
    }
    (DATA / "board.json").write_text(json.dumps(board, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (DATA / "status.json").write_text(json.dumps({"captured_at": board["captured_at"], "status": status,
                                                  "counts": board["counts"]}, indent=2), encoding="utf-8")
    (DATA / "quarantine.json").write_text(json.dumps(quarantine[:500], ensure_ascii=False, indent=1), encoding="utf-8")
    with (DATA / "observations.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(to_dict(observations[0]).keys()) if observations else ["operator"])
        w.writeheader()
        for o in observations:
            w.writerow(to_dict(o))
    print(f"wrote data/board.json ({len(board_fixtures)} fixtures) and data/observations.csv ({len(observations)} rows)")
    return 0 if len(operators) >= MIN_BOOKS_FOR_CONSENSUS else 1


if __name__ == "__main__":
    sys.exit(main())
