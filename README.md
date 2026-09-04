# The Hundred Bob Finder

Design document and working prototype for a bettor-facing odds-comparison app for Kenya, with a
live capture of three operators' public prices.

The app reads licensed operators' prices, strips the margin to get a consensus probability for each
outcome, finds the best price across operators, and shows the cash that comes back to M-Pesa after
the 5% deposit excise and the 5% withdrawal excise. It never holds money or places bets: it hands the
bettor to the operator's own app or site with the slip prepared.

**Live page:** https://gaeskat.github.io/hundred-bob-finder/

## What is here

- `index.html` - the design (pipeline, probability engine, returns engine, hand-off, accumulator
  builder, build sequence) and the finder, which runs entirely in the browser. When
  `data/board.json` is present beside it, the finder shows the live board and its capture time;
  otherwise it shows an illustrative board of real clubs with invented prices, and says so.
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
