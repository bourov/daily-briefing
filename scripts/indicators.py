#!/usr/bin/env python3
"""Scrape supplementary market indicators from public web sources.

No LLM needed — deterministic web scraping with BeautifulSoup.
"""

import re
import sys

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; daily-briefing/1.0)"
}


def scrape_fear_greed() -> dict:
    """Fetch CNN Fear & Greed Index value."""
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            score = data.get("fear_and_greed", {}).get("score")
            prev = data.get("fear_and_greed_historical", {}).get("one_week_ago", {}).get("score")
            month = data.get("fear_and_greed_historical", {}).get("one_month_ago", {}).get("score")
            if score is not None:
                return {
                    "current_value": round(score),
                    "1_week_ago": round(prev) if prev else None,
                    "1_month_ago": round(month) if month else None,
                    "category": _fg_category(score),
                }
    except Exception as exc:
        print(f"Warning: Fear & Greed fetch failed: {exc}", file=sys.stderr)

    # Fallback: try alternate endpoint
    try:
        url = "https://fear-and-greed-index.p.rapidapi.com/v1/fgi"
        resp = requests.get(
            "https://edition.cnn.com/markets/fear-and-greed",
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code == 200:
            match = re.search(r'"score"\s*:\s*(\d+)', resp.text)
            if match:
                score = int(match.group(1))
                return {"current_value": score, "category": _fg_category(score)}
    except Exception:
        pass

    return {"current_value": None, "category": "Unknown"}


def _fg_category(score: float) -> str:
    if score <= 25:
        return "Extreme Fear"
    if score <= 45:
        return "Fear"
    if score <= 55:
        return "Neutral"
    if score <= 75:
        return "Greed"
    return "Extreme Greed"


def scrape_cape() -> dict:
    """Scrape Shiller CAPE ratio from multpl.com."""
    try:
        resp = requests.get(
            "https://www.multpl.com/shiller-pe",
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            val_el = soup.select_one("#current")
            if val_el:
                text = val_el.get_text(strip=True)
                match = re.search(r"[\d.]+", text)
                if match:
                    return {"current_value": float(match.group())}
    except Exception as exc:
        print(f"Warning: CAPE scrape failed: {exc}", file=sys.stderr)
    return {"current_value": None}


def scrape_buffett_indicator() -> dict:
    """Scrape Buffett Indicator from currentmarketvaluation.com."""
    try:
        resp = requests.get(
            "https://www.currentmarketvaluation.com/models/buffett-indicator.php",
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code == 200:
            # Look for "Buffett Indicator as NNN%"
            match = re.search(r"Buffett\s+Indicator\s+as\s+([\d,.]+)\s*%", resp.text, re.IGNORECASE)
            if match:
                return {"current_value": float(match.group(1).replace(",", ""))}
            # Fallback: "ratio of total US stock market valuation to GDP" context
            match = re.search(r"valuation\s+to\s+GDP[^%]*?([\d,.]+)\s*%", resp.text)
            if match:
                val = float(match.group(1).replace(",", ""))
                if val > 50:  # Buffett Indicator should be >50%
                    return {"current_value": val}
    except Exception as exc:
        print(f"Warning: Buffett Indicator scrape failed: {exc}", file=sys.stderr)
    return {"current_value": None}


def scrape_market_breadth() -> dict:
    """Scrape market breadth indicators."""
    result = {
        "above_50dma": None,
        "above_200dma": None,
        "advance_decline": None,
    }

    try:
        resp = requests.get(
            "https://www.barchart.com/stocks/indices/sp-tsx-composite/percent-above-moving-averages",
            headers={**HEADERS, "Accept": "text/html"},
            timeout=15,
        )
        if resp.status_code == 200:
            match50 = re.search(r"50-Day.*?([\d.]+)%", resp.text, re.DOTALL)
            match200 = re.search(r"200-Day.*?([\d.]+)%", resp.text, re.DOTALL)
            if match50:
                result["above_50dma"] = float(match50.group(1))
            if match200:
                result["above_200dma"] = float(match200.group(1))
    except Exception as exc:
        print(f"Warning: breadth scrape failed: {exc}", file=sys.stderr)

    return result


def scrape_put_call_ratio() -> dict:
    """Get put/call ratio from CBOE or fallback source."""
    try:
        resp = requests.get(
            "https://www.cboe.com/us/options/market_statistics/",
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code == 200:
            match = re.search(r"equity\s+put/call.*?([\d.]+)", resp.text, re.IGNORECASE | re.DOTALL)
            if match:
                return {"current_value": float(match.group(1))}
    except Exception:
        pass
    return {"current_value": None}


def fetch_all_indicators() -> dict:
    """Fetch all supplementary indicators."""
    return {
        "fear_greed": scrape_fear_greed(),
        "cape": scrape_cape(),
        "buffett": scrape_buffett_indicator(),
        "breadth": scrape_market_breadth(),
        "put_call": scrape_put_call_ratio(),
    }
