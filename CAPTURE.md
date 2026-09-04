# The capture pipeline

`python -m capture.run` reads the public pre-match football feeds of the Kenyan operators
below, joins the same fixture across them, and writes the board the page loads.

## Operators

| Operator | Feed | Window | Notes |
|---|---|---|---|
| Betika | `api.betika.com/v1/uo/matches` (1X2, next 48 h, paged by 100) | 48 h | robots.txt of the site allows all; the API host has no robots file (404), which the standard reads as no restriction |
| SportyBet Kenya | `sportybet.com/api/ke/factsCenter/pcUpcomingEvents` with `timeline=48`, 100 per page | 48 h | robots.txt allows the feed path |
| Odibets | `odibets.com/pxy2/sportsbook?resource=sport&sport_id=1&day=YYYY-MM-DD&competition_id=…` | per day in the window | the day feed serves only a first slice, so the adapter reads the day's competition list and fetches the largest competitions plus the core leagues (cap 32 requests per day) |

Not captured, and why:

- **SportPesa** answers every request, including `robots.txt`, with an Akamai bot challenge. Getting past a challenge is evasion, not capture, so it is out.
- **Betway Kenya** returned HTTP 523 (origin unreachable) at discovery time.
- **Mozzart, Shabiki, Pepeta, Bangbet** load their boards through in-page proxy endpoints that were not identified from public requests. Adapters can be added once an endpoint is known; the same conduct rules apply.

## Conduct

- Public feeds only. No login, no session cookie, no page automation, no bettor credentials.
- Identified user agent: `HundredBobFinder/0.1 (+https://github.com/GaeskaT/hundred-bob-finder; …)`.
- At most one request per second per host. A capture is about 60–90 requests in total.
- `robots.txt` is fetched once per host and honoured for this user agent. A host that refuses robots (401/403 or a challenge page) is treated as refusing everything.
- An adapter that fails is reported as degraded in `data/status.json` and on the page; nothing is estimated in its place.
- Operator terms of use have **not** been reviewed by a lawyer. Section 7 of the design makes that a gate before an adapter is relied on. This repository runs the capture as a public-interest price comparison; if an operator objects, its adapter is switched off.

## Evidence

Every observation in `data/observations.csv` carries: operator, sport, country, league, home, away,
kick-off (UTC), market, outcome, price, source URL, observed-at (UTC), the archived raw response it
came from (`data/raw/…`), and the collector. Rows missing any field are dropped, never estimated.

`data/raw/` holds the raw responses of the latest capture only; the workflow overwrites them each run.

## Matching

Two operators' rows are the same fixture when both team names agree after normalisation (club-form
suffixes dropped, aliases applied) and the kick-offs are within 30 minutes. If one team agrees exactly
and the kick-off agrees, a looser match on the other team is accepted ("PSV" against "PSV Eindhoven").
Gender and age markers ("W", "Women", "U21") are never dropped: a women's side is a different team
from the men's side of the same club. Rows that match on one team only go to `data/quarantine.json`
for a human to extend the alias table in `capture/match.py`.

## The board

`data/board.json` has the same shape as the page's illustrative board: per fixture, the three 1X2
prices at each operator, or `null` where an operator does not price it. The page loads it when
present and shows the capture time; otherwise it stays on the illustrative board and says so.

## Schedule, and the Kenyan machine

`.github/workflows/capture.yml` runs every 30 minutes on GitHub's runners and deploys the page plus
the board to Pages as an artifact; nothing is committed per capture. Measured on the first run
(2026-09-04): Betika and Odibets answer the runners normally; **SportyBet refuses its robots file to
the runner's address** while allowing it from Kenya, so from the cloud alone the board has two
operators and no consensus.

So there is a second path. On a Kenyan machine:

```
python -m capture.publish
```

runs the capture and force-pushes only `board.json`, `status.json` and `quarantine.json` as a single
orphan commit to the `data` branch (history never grows). On its next run the workflow fetches that
branch and `capture.choose` deploys the Kenyan board when it is fresher than 90 minutes and priced
by more operators than the cloud capture; otherwise the cloud board stands. `status.json` records
which was deployed and why, and the page's banner says it. Put `capture.publish` on a schedule
(Task Scheduler, cron) every 30 minutes to keep three operators on the live page.
