#!/usr/bin/env python3
"""Daily briefing & crash dashboard generator.

Orchestrates weather, news, market data, and indicator fetching,
then generates daily/index.html and crash/crash_indicators_data.json.

No LLM required — all content is deterministic.
"""

import json
import os
import sys

# Add parent dir so we can run as `python scripts/main.py` from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scripts.weather import fetch_weather, format_weather
from scripts.news import fetch_all_news
from scripts.market_data import fetch_market_data
from scripts.indicators import fetch_all_indicators
from scripts.crash_json import build_crash_json
from scripts.briefing_html import render_briefing, get_austin_time

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")


def main():
    print("=" * 60)
    print("Daily Briefing & Crash Dashboard Generator")
    print("=" * 60)

    austin_now, tz_abbr = get_austin_time()
    date_str = austin_now.strftime("%B %-d, %Y")
    print(f"Date: {date_str} ({tz_abbr})")

    # --- Fetch all data ---
    print("\n[1/5] Fetching weather data from weather.gov ...")
    raw_weather = fetch_weather()
    weather = format_weather(raw_weather, date_str)
    print(f"  Weather: {'OK' if weather['available'] else 'FAILED (will show placeholder)'}")

    print("\n[2/5] Fetching news via RSS feeds ...")
    news = fetch_all_news()
    for cat, items in news.items():
        print(f"  {cat}: {len(items)} articles")

    print("\n[3/5] Fetching market data from Yahoo Finance ...")
    market_data = fetch_market_data()
    for key, val in market_data.items():
        if isinstance(val, dict):
            print(f"  {key}: {json.dumps(val, indent=None)[:80]}...")
        else:
            print(f"  {key}: {val}")

    print("\n[4/5] Fetching supplementary indicators ...")
    indicators = fetch_all_indicators()
    for key, val in indicators.items():
        print(f"  {key}: {val}")

    # --- Generate outputs ---
    print("\n[5/5] Generating output files ...")

    # Daily briefing HTML
    html = render_briefing(weather, news)
    daily_dir = os.path.join(OUTPUT_DIR, "daily")
    os.makedirs(daily_dir, exist_ok=True)
    daily_path = os.path.join(daily_dir, "index.html")
    with open(daily_path, "w", encoding="utf-8") as f:
        f.write(html)
        if not html.endswith("\n"):
            f.write("\n")
    print(f"  Written: {daily_path}")

    # Crash dashboard JSON
    crash_data = build_crash_json(market_data, indicators)
    crash_dir = os.path.join(OUTPUT_DIR, "crash")
    os.makedirs(crash_dir, exist_ok=True)
    crash_path = os.path.join(crash_dir, "crash_indicators_data.json")
    with open(crash_path, "w", encoding="utf-8") as f:
        json.dump(crash_data, f, indent=2)
        f.write("\n")
    print(f"  Written: {crash_path}")

    print("\nDone!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
