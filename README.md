# Daley Valuations

Source for [daleyvaluations.com](https://daleyvaluations.com), the equity research site behind [Neil Daley](https://www.etoro.com/people/dalkent13)'s FTSE valuation work.

The site is a static, weekly-refreshed reference covering the FTSE stocks in the model, valued with DCF, DDM and earnings models blended by business type, with separate models for financials. The full methodology lives at [/methodology](https://daleyvaluations.com/methodology).

## What this repo is

Just the static front-end. HTML, CSS, no JavaScript framework, no build step. The data that drives the signals is generated weekly by a separate, private pipeline that runs the valuation script against live market data and produces the JSON files this site reads. That pipeline is not in this repo.

## What this repo is not

Not the valuation engine. Not a way to copy the methodology. The numbers on the live site come from a model I have built and refined over a decade. The methodology page documents what the model does. It does not give you the implementation.

## Local development

Clone the repo. Open `index.html` in any browser. That is the entire dev loop.

```
git clone https://github.com/<your-username>/daleyvaluations-site.git
cd daleyvaluations-site
open index.html  # or just double-click in your file manager
```

No `npm install`, no build tools, no Docker. The whole thing is one self-contained HTML file with embedded CSS.

## Deployment

The live site is deployed via [Cloudflare Pages](https://pages.cloudflare.com/) directly from this repo. Every push to `main` triggers a rebuild and a deploy in seconds. Cloudflare also handles the DNS, the SSL certificate, and the CDN.

To deploy a change: edit, commit, push. That is it.

## Keeping the methodology page in step

`methodology_source.html` is a Jinja fragment. Its numbers are read from the model's `valuation.py` and `signals.py` at build time, and its `data-methodology-version` stamp must equal the `version:` of the vault document *Valuation Methodology*. If the document has moved on, `build_site.py` stops with an error: update the page prose, then the stamp.

## Author

[Neil Daley](https://www.etoro.com/people/dalkent13). PhD, CFA. Twenty years in institutional finance. eToro Popular Investor. UK-based.

## Licence

The HTML/CSS code in this repo is MIT licensed. The methodology content, written prose, and any article text on the site are all rights reserved. See [LICENSE](LICENSE) for the full text.
