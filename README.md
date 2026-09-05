# The Hundred Bob Finder

Design document and working prototype for a bettor-facing odds-comparison app for Kenya, with a
live capture of three operators' public prices.

The app reads licensed operators' prices, strips the margin to get a consensus probability for each
outcome, finds the best price across operators, and shows the cash that comes back to M-Pesa after
the 5% deposit excise and the 5% withdrawal excise. It never holds money or places bets: it hands the
bettor to the operator's own app or site with the slip prepared in that operator's own
wording (its team spellings, market name and outcome labels), so it can be copied straight in,
and a deep link that opens the operator's app (or site) at that fixture.

**Live page:** https://gaeskat.github.io/hundred-bob-finder/

## What is here

- `index.html` - the design (pipeline, probability engine, returns engine, hand-off, accumulator
  builder, build sequence) and the finder, which runs entirely in the browser: operator filter
  (the board is recomputed from the operators left on), market filter (1X2 or Over/Under 2.5), league filter,
  kick-off day filter (Today / Tomorrow / the day after, Nairobi time), fixture search (every word typed must appear in the fixture, outcome or league), three sorts,
  the pick of the board, the hand-off card and the accumulator builder. When
  `data/board.json` is present beside it, the finder shows the live board and its capture time;
  otherwise it shows an illustrative board of real clubs with invented prices, and says so.
  - Hand-off card: the slip in the operator's own wording, an Open button that is the operator's
    fixture page (an Android intent naming its app, with the site as fallback), one link per leg
    for an accumulator, Copy slip, and Copy links (every operator's page for the fixture, plain
    https, ready to share).
  - 75% floor, always: the finder only shows outcomes whose consensus chance of winning is 75% or
    more. The probability slider starts at 75% and can only be raised.
  - Floor multi: raise the minimum probability (75%, 80%, 85%...) and every outcome at or above it,
    one per fixture, is highlighted and combined into one multi-bet per operator with combined
    odds, what it pays to M-Pesa if every leg wins, and the chance of that; capped at the 20
    likeliest legs. Take it to the operator, load it into the builder, or Share it (phone share
    sheet, or clipboard) with a link that reopens the same floor.
  - Independent opinions: operators carrying identical prices on a fixture count as one source in
    the consensus and in the pick's three-source rule; counts read "n=3 · 2 independent". A pick
    whose edge exists at one operator only is labelled "one operator disagrees", with the next-best
    price and its expected value beside it, instead of "value found".
- `capture/` - the capture pipeline: one adapter per operator, a polite HTTP client (identified
  user agent, one request per second per host, robots honoured), the fixture matcher, and the
  board writer. See [CAPTURE.md](CAPTURE.md) for operators, conduct, evidence fields and matching.
- `.github/workflows/capture.yml` - runs the capture every 30 minutes and deploys the page plus the
  fresh board to GitHub Pages as an artifact, so the repository's history does not grow.

## Operators captured

Betika, SportyBet Kenya and Odibets, football 1X2, fixtures kicking off within 48 hours. Three is
the minimum for a consensus. SportPesa is behind a bot challenge and is not captured on purpose;
the others are listed in CAPTURE.md with the reason each is absent.

## Running it

```
python -m capture.run          # writes data/board.json, data/observations.csv, data/status.json,
                               # data/quarantine.json and data/raw/*.json (about 90 seconds)
```

Then open `index.html` in a browser from a local web server (the board is fetched, so `file://`
falls back to the illustrative board). No dependencies beyond Python 3.11+ and Google Fonts.

## What the numbers are, and are not

- Prices are the operators' own public pre-match offers at the capture time printed on the page.
  They move; the operator's app prices the bet live when you get there.
- Probability is the median de-vigged view across the operators quoting the fixture. It is the
  market's opinion with the margin removed, not a prediction.
- Expected value is negative on almost every row. The page says so rather than hiding it.

## Status

v0.8, design for review with a live capture. Not legal advice; operator terms of use have not been
reviewed by a lawyer, which the design itself makes a gate. See the footer of the page.

## Licence

Code and text: MIT. Observations: CC BY 4.0.
