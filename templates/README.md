# Templates

Jinja2 templates for the build pipeline. Stage 2 will populate these.

| Template | Renders | Status |
|---|---|---|
| `tracker.html` | Homepage with the 114-stock table | Pending |
| `ticker.html` | One per-ticker page (rendered 114 times with different data) | Pending |
| `methodology.html` | The methodology page at /methodology | Pending |
| `_layout.html` | Shared header, navigation, footer (included by all the above) | Pending |

The current live `index.html` (methodology page) does not yet use these templates. When Stage 2 lands, the methodology content moves into `methodology.html` and a new generated `index.html` becomes the tracker page.

## Why we are not using the existing editorial_theme.py

The `eToro/scripts/editorial_theme.py` module ships shared CSS for Neil's internal dashboards (portfolio dashboard, factsheets, etc). Those use a terracotta + cream palette that does not match the public Daley Valuations brand (deep forest + ivory). The two design languages are deliberately different.

The build pipeline reuses helper functions from `editorial_theme.py` where they are brand-neutral (e.g. `signal_for()`, number formatters), but writes its own CSS to the public-brand palette.
