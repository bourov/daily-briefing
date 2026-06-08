#!/usr/bin/env python3
"""Fetch news articles via RSS feeds — no LLM needed.

Uses Google News RSS and direct publication RSS feeds.
"""

import re
import sys
from datetime import datetime, timedelta, timezone
from html import unescape
from urllib.parse import quote_plus

import feedparser
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; daily-briefing/1.0)"}


# --- Positive sentiment keywords ---
POSITIVE_WORDS = {
    "growth", "growing", "record", "boost", "success", "win", "winning",
    "launch", "cooperation", "partnership", "innovation", "development",
    "invest", "investment", "expand", "achievement", "agreement", "deal",
    "improve", "improvement", "progress", "advance", "breakthrough",
    "celebrate", "festival", "tourism", "cultural", "sport", "champion",
    "recovery", "increase", "positive", "optimistic", "milestone",
    "humanitarian", "peace", "harvest", "construction", "opening",
}

# --- Negative / conflict keywords (not positive) ---
NEGATIVE_WORDS = {
    "attack", "strike", "bomb", "kill", "dead", "death", "war", "missile",
    "sanctions", "conflict", "crisis", "threat", "arrest", "detained",
    "crash", "fire", "explosion", "casualty", "casualties", "protest",
    "decline", "collapse", "destroy", "damage", "escalat",
}


def _clean_title(title: str) -> str:
    """Strip HTML tags and decode entities from RSS title."""
    title = unescape(title)
    title = re.sub(r"<[^>]+>", "", title)
    return title.strip()


def _is_fresh(entry, cutoff: datetime) -> bool:
    """Check if entry was published within the cutoff window."""
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    if published:
        try:
            pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
            return pub_dt >= cutoff
        except Exception:
            pass
    return True  # If no date, assume fresh


def _classify_sentiment(title: str) -> str:
    """Rule-based sentiment: 'positive' or 'neutral'."""
    lower = title.lower()
    pos_count = sum(1 for w in POSITIVE_WORDS if w in lower)
    neg_count = sum(1 for w in NEGATIVE_WORDS if w in lower)
    if pos_count > neg_count and pos_count >= 1:
        return "positive"
    return "neutral"


def _fetch_rss(url: str, max_items: int = 20) -> list[dict]:
    """Fetch and parse an RSS feed, returning list of article dicts."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return []
        feed = feedparser.parse(resp.text)
        articles = []
        for entry in feed.entries[:max_items]:
            title = _clean_title(entry.get("title", ""))
            link = entry.get("link", "")
            source = entry.get("source", {}).get("title", "")
            if not source:
                # Try to extract source from Google News title format "Title - Source"
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    if len(parts) == 2 and len(parts[1]) < 60:
                        title, source = parts
            published = entry.get("published", "")
            articles.append({
                "title": title.strip(),
                "url": link,
                "source": source.strip(),
                "published": published,
            })
        return articles
    except Exception as exc:
        print(f"Warning: RSS fetch failed for {url}: {exc}", file=sys.stderr)
        return []


def _google_news_rss(query: str, when: str = "1d") -> list[dict]:
    """Search Google News RSS for a query within a time window."""
    encoded = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded}+when:{when}&hl=en-US&gl=US&ceid=US:en"
    return _fetch_rss(url)


def _google_news_rss_ru(query: str, when: str = "1d") -> list[dict]:
    """Search Google News RSS in Russian."""
    encoded = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded}+when:{when}&hl=ru&gl=RU&ceid=RU:ru"
    return _fetch_rss(url)


def _deduplicate(articles: list[dict]) -> list[dict]:
    """Remove duplicate articles by similar titles."""
    seen = set()
    unique = []
    for a in articles:
        # Normalize: lowercase, remove punctuation, keep first 50 chars
        key = re.sub(r"[^\w\s]", "", a["title"].lower())[:50]
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique


# --- Excluded source domains / keywords ---
_EXCLUDED_SOURCES = {
    "moscow times", "themoscowtimes",
    "kyiv independent", "kyivindependent",
    "ukrainska pravda", "pravda.com.ua",
    "ukrinform", "unian", "liga.net",
    "euromaidan", "euromaidan press",
    "ukraine pravda", "ukrainian truth",
    "ukrayinska pravda",
}

_UKRAINE_GOV_KEYWORDS = {
    "zelensky", "zelenskyy", "zelenskiy",
    "ukrainian government", "ukraine government",
    "ukrainian ministry", "ukraine ministry",
    "ukrainian president", "ukraine's president",
    "ukrainian foreign minister", "ukrainian defense",
    "ukrainian military", "ukraine military",
    "kyiv says", "kyiv claims",
}


def _is_excluded_source(article: dict) -> bool:
    """Check if article is from an excluded source or references Ukrainian gov."""
    source = article.get("source", "").lower()
    url = article.get("url", "").lower()
    title = article.get("title", "").lower()

    for excl in _EXCLUDED_SOURCES:
        if excl in source or excl in url:
            return True

    for kw in _UKRAINE_GOV_KEYWORDS:
        if kw in title or kw in source:
            return True

    return False


def _exclude_sources(articles: list[dict]) -> list[dict]:
    """Filter out excluded sources (Moscow Times, Ukrainian outlets/gov refs)."""
    return [a for a in articles if not _is_excluded_source(a)]


def fetch_russia_news() -> tuple[list[dict], list[dict]]:
    """Fetch Russia news and split into positive and neutral categories."""
    articles = []

    # TASS English
    articles.extend(_google_news_rss("Russia TASS positive news"))
    articles.extend(_google_news_rss("Russia economy growth development"))
    articles.extend(_google_news_rss("Russia news today"))
    articles.extend(_google_news_rss("Russia Reuters"))

    articles = _exclude_sources(articles)
    articles = _deduplicate(articles)

    positive = []
    neutral = []
    for a in articles:
        sentiment = _classify_sentiment(a["title"])
        if sentiment == "positive":
            positive.append(a)
        else:
            neutral.append(a)

    return positive[:3], neutral[:4]


def fetch_spb_news() -> list[dict]:
    """Fetch St. Petersburg news in English and Russian."""
    en_articles = _google_news_rss('"Saint Petersburg" Russia')
    ru_articles = _google_news_rss_ru("Санкт-Петербург новости")

    for a in en_articles:
        a["lang"] = "EN"
    for a in ru_articles:
        a["lang"] = "RU"

    # Fontanka RSS
    fontanka = _fetch_rss("https://www.fontanka.ru/fontanka.rss", max_items=5)
    for a in fontanka:
        a["lang"] = "RU"

    all_articles = _exclude_sources(_deduplicate(en_articles + ru_articles + fontanka))
    # Aim for mix: ~3 EN, ~3 RU
    en = [a for a in all_articles if a.get("lang") == "EN"][:3]
    ru = [a for a in all_articles if a.get("lang") == "RU"][:3]
    return (en + ru)[:6]


def fetch_klac_news() -> list[dict]:
    """Fetch KLA Corporation (KLAC) news."""
    articles = _google_news_rss('"KLA Corporation" OR KLAC stock')
    articles.extend(_google_news_rss("KLAC semiconductor"))
    return _deduplicate(articles)[:5]


def fetch_cpo_news() -> list[dict]:
    """Fetch Co-Packaged Optics news."""
    articles = _google_news_rss('"co-packaged optics" OR CPO semiconductor')
    return _deduplicate(articles)[:2]


def fetch_all_news() -> dict:
    """Fetch all news categories."""
    positive, neutral = fetch_russia_news()
    return {
        "positive_russia": positive,
        "neutral_russia": neutral,
        "spb": fetch_spb_news(),
        "klac": fetch_klac_news(),
        "cpo": fetch_cpo_news(),
    }
