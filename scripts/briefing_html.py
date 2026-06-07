#!/usr/bin/env python3
"""Render daily/index.html from Jinja2 template — no LLM needed."""

import os
from datetime import datetime, timedelta, timezone

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def get_austin_time() -> datetime:
    """Return current time in Austin, TX (Central Time)."""
    # CDT = UTC-5 (March-November), CST = UTC-6 (November-March)
    # Simplified: use -5 for CDT season (March-November)
    utc_now = datetime.now(timezone.utc)
    month = utc_now.month
    if 3 <= month <= 10:
        offset = timedelta(hours=-5)
        tz_abbr = "CDT"
    else:
        offset = timedelta(hours=-6)
        tz_abbr = "CST"
    return utc_now.astimezone(timezone(offset)), tz_abbr


def render_briefing(weather: dict, news: dict) -> str:
    """Render the daily briefing HTML from template and data."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=True,
    )
    template = env.get_template("briefing.html")

    austin_now, tz_abbr = get_austin_time()
    date_long = austin_now.strftime("%B %-d, %Y")
    day_of_week = austin_now.strftime("%A")

    return template.render(
        date_long=date_long,
        day_of_week=day_of_week,
        tz_abbr=tz_abbr,
        weather=weather,
        news=news,
    )
