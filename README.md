# The Hundred Bob Finder

Design document and working prototype for a bettor-facing odds-comparison app for Kenya.

The app reads every licensed operator's prices, strips the margin to get a consensus probability for each outcome, finds the best price across operators, and shows the cash that comes back to M-Pesa after the 5% deposit excise and the 5% withdrawal excise. It never holds money or places bets: it hands the bettor to the operator's own app or site with the slip prepared.

**Live page:** https://gaeskat.github.io/hundred-bob-finder/

## What is here

- `index.html` - the whole thing: the design (pipeline, probability engine, returns engine, hand-off, accumulator builder, build sequence) and the prototype finder, which runs entirely in the browser.

## What the prototype is, and is not

- Every figure on the page is computed live from the raw prices in the page's own data.
- The prices are **illustrative** and the four operators are unnamed (Book A-D) on purpose. No real operator has been measured. Attaching invented prices to a real name would be the error the design exists to avoid.
- There is no scraper in this repository. The capture pipeline in section 2 is the design for one; building it is Phase 0 of section 11.

## Running it

Open `index.html` in a browser. No build, no server, no dependencies beyond Google Fonts.

## Status

v0.6, design for review. Not legal advice; see the footer of the page.

## Licence

Code and text: MIT.
