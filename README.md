# Daily Briefing & Crash Dashboard

Automated daily generation of:
- **`daily/index.html`** — Morning briefing with Austin weather, Russia/St. Petersburg news, and KLAC/CPO semiconductor news
- **`crash/crash_indicators_data.json`** — Market crash indicators dashboard with VIX, S&P 500, CAPE, Buffett Indicator, and more

## Architecture

**100% LLM-free** — all data comes from deterministic sources:

| Component | Source |
|---|---|
| Weather | [weather.gov](https://api.weather.gov) API |
| VIX, S&P 500, Yields | [Yahoo Finance](https://finance.yahoo.com) via `yfinance` |
| News | Google News RSS, TASS, Fontanka.ru, Sputnik |
| CAPE Ratio | [multpl.com](https://www.multpl.com/shiller-pe) |
| Buffett Indicator | [currentmarketvaluation.com](https://www.currentmarketvaluation.com) |
| Fear & Greed Index | CNN API |
| Crash Probability | Rules-based algorithm with historical base rates |
| HTML Rendering | Jinja2 templates |

## Usage

```bash
pip install -r requirements.txt
python scripts/main.py
```

Output is written to `output/daily/index.html` and `output/crash/crash_indicators_data.json`.

## GitHub Actions

Runs daily at 11:00 UTC (6:00 AM CDT). Requires `PAGES_REPO_TOKEN` secret with push access to `bourov/bourov.github.io`.

Manual trigger: Actions → Daily Update → Run workflow.

## Project Structure

```
scripts/
├── main.py              # Orchestrator
├── weather.py           # weather.gov API
├── news.py              # RSS feed aggregation + sentiment classification
├── market_data.py       # yfinance: VIX, S&P 500, yields
├── indicators.py        # Web scraping: CAPE, Buffett, Fear&Greed
├── crash_probability.py # Rules-based crash probability engine
├── crash_json.py        # Crash dashboard JSON assembly
├── briefing_html.py     # Jinja2 HTML rendering
└── templates/
    └── briefing.html    # HTML template
data/
└── static_data.json     # Slowly-changing data (margin debt, private credit)
```
