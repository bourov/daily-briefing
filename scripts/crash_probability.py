#!/usr/bin/env python3
"""Rules-based crash probability engine — no LLM needed.

Estimates probability of ≥20% drawdown from current S&P 500 level
across 5-day, 20-day, and 60-day horizons. Uses historical base
rates adjusted by current indicator readings.
"""


# Historical base rates for ≥20% drawdown (annualized ~5%, adjusted per window)
BASE_RATES = {"5_day": 0.1, "20_day": 1.5, "60_day": 4.0}


def _vix_multiplier(vix: float) -> float:
    """Higher VIX → higher crash probability multiplier."""
    if vix < 12:
        return 0.5  # Very calm, complacent
    if vix < 16:
        return 0.8
    if vix < 20:
        return 1.0
    if vix < 25:
        return 1.5
    if vix < 30:
        return 2.5
    if vix < 40:
        return 4.0
    return 6.0


def _rsi_multiplier(rsi: float) -> float:
    """Overbought RSI increases correction probability."""
    if rsi > 80:
        return 1.8
    if rsi > 70:
        return 1.3
    if rsi > 60:
        return 1.0
    if rsi > 40:
        return 0.8
    return 1.2  # Oversold can also be risky (momentum breakdown)


def _cape_multiplier(cape: float | None) -> float:
    """Extreme valuations increase vulnerability."""
    if cape is None:
        return 1.0
    if cape > 40:
        return 2.0
    if cape > 35:
        return 1.6
    if cape > 30:
        return 1.3
    if cape > 25:
        return 1.1
    return 0.8


def _buffett_multiplier(buffett: float | None) -> float:
    """Buffett Indicator extremes."""
    if buffett is None:
        return 1.0
    if buffett > 200:
        return 1.8
    if buffett > 150:
        return 1.4
    if buffett > 115:
        return 1.1
    return 0.8


def _drawdown_multiplier(drawdown_pct: float) -> float:
    """Already in drawdown may mean selling momentum."""
    if drawdown_pct > 15:
        return 2.0
    if drawdown_pct > 10:
        return 1.5
    if drawdown_pct > 5:
        return 1.2
    if drawdown_pct == 0:
        return 1.1  # At ATH — slight elevation for "room to fall"
    return 1.0


def _breadth_multiplier(above_200dma: float | None) -> float:
    """Breadth divergence when index is near ATH."""
    if above_200dma is None:
        return 1.0
    if above_200dma < 40:
        return 1.6
    if above_200dma < 55:
        return 1.3
    if above_200dma < 65:
        return 1.1
    return 0.9


def _leverage_multiplier(margin_debt_yoy_growth: float | None) -> float:
    """Record margin debt growth increases forced-selling risk."""
    if margin_debt_yoy_growth is None:
        return 1.0
    if margin_debt_yoy_growth > 40:
        return 1.5
    if margin_debt_yoy_growth > 20:
        return 1.2
    return 1.0


def compute_crash_probability(
    vix: float = 20.0,
    rsi: float = 50.0,
    cape: float | None = None,
    buffett: float | None = None,
    drawdown_from_ath_pct: float = 0.0,
    above_200dma_pct: float | None = None,
    margin_debt_yoy_pct: float | None = None,
) -> dict:
    """Compute crash probability for 5d, 20d, 60d horizons."""
    results = {}

    for horizon, base in BASE_RATES.items():
        # Time-scale factor: near-term multipliers matter less for short horizons
        if horizon == "5_day":
            mult = (
                _vix_multiplier(vix) ** 1.5
                * _rsi_multiplier(rsi) ** 0.5
            )
        elif horizon == "20_day":
            mult = (
                _vix_multiplier(vix)
                * _rsi_multiplier(rsi)
                * _cape_multiplier(cape) ** 0.5
                * _drawdown_multiplier(drawdown_from_ath_pct)
            )
        else:  # 60_day
            mult = (
                _vix_multiplier(vix) ** 0.5
                * _rsi_multiplier(rsi)
                * _cape_multiplier(cape)
                * _buffett_multiplier(buffett)
                * _breadth_multiplier(above_200dma_pct) ** 0.5
                * _leverage_multiplier(margin_debt_yoy_pct)
                * _drawdown_multiplier(drawdown_from_ath_pct) ** 0.5
            )

        prob = min(base * mult, 95.0)  # Cap at 95%
        prob = round(prob, 1)

        # Confidence: higher when more data is available
        confidence = 5
        if vix and cape and buffett:
            confidence = 7
        if above_200dma_pct:
            confidence += 1
        confidence = min(confidence, 9)

        # Key drivers
        drivers = _key_drivers(horizon, vix, rsi, cape, buffett,
                               drawdown_from_ath_pct, above_200dma_pct,
                               margin_debt_yoy_pct)

        # Interpretation
        interp = _interpretation(horizon, prob, vix, rsi, cape)

        results[horizon] = {
            "probability_pct": prob,
            "confidence": confidence,
            "key_drivers": drivers,
            "interpretation": interp,
        }

    results["methodology"] = (
        "Based on current VIX level, technical indicators, macro conditions, "
        "historical base rates, and market structure analysis."
    )
    return results


def _key_drivers(horizon, vix, rsi, cape, buffett, drawdown, breadth, leverage):
    drivers = []
    if vix < 16:
        drivers.append(f"VIX at {vix} — well below stress threshold of 25+")
    elif vix > 25:
        drivers.append(f"VIX at {vix} — elevated fear signals stress")

    if rsi > 70:
        drivers.append(f"RSI at {rsi} — overbought territory")
    elif rsi < 30:
        drivers.append(f"RSI at {rsi} — oversold")

    if cape and cape > 35:
        drivers.append(f"CAPE at {cape} — near historical extremes (dot-com peak was 44.2)")
    if buffett and buffett > 150:
        drivers.append(f"Buffett Indicator at {buffett}% — significantly overvalued")
    if drawdown == 0:
        drivers.append("S&P 500 at or near all-time high")
    if breadth and breadth < 60:
        drivers.append(f"Only {breadth}% of S&P 500 above 200dma — breadth divergence")
    if leverage and leverage > 30:
        drivers.append(f"Margin debt growing {leverage}% YoY — elevated leverage")

    return drivers[:5] if drivers else ["No extreme signals detected"]


def _interpretation(horizon, prob, vix, rsi, cape):
    risk_word = "extremely low" if prob < 2 else "low" if prob < 5 else "moderate" if prob < 10 else "elevated" if prob < 20 else "high"
    period = {"5_day": "5-day", "20_day": "20-day", "60_day": "60-day"}[horizon]
    return f"{risk_word.title()} {period} crash risk at {prob}%. Historical base rate adjusted for current VIX ({vix}), RSI ({rsi}){f', CAPE ({cape})' if cape else ''}."


# ---------------------------------------------------------------------------
# Ray Dalio-style Bubble Indicator (rules-based proxy)
# ---------------------------------------------------------------------------
# Approximates Dalio's 6-gauge framework using publicly available data.
# Each gauge scores 0–100 (0 = no bubble signal, 100 = extreme bubble).
# Composite is an equal-weighted average.
#
# Reference levels:
#   1929 peak composite ≈ 100,  2000 dot-com peak ≈ 100
#   2021 meme-stock era ≈ 73,   typical non-bubble ≈ 20-40
# ---------------------------------------------------------------------------

def _gauge_prices_vs_traditional(cape: float | None, buffett: float | None) -> float:
    """Gauge 1: How high are prices relative to traditional measures?"""
    score = 0.0
    if cape is not None:
        # CAPE: mean ~17, dot-com peak ~44
        score += min((cape - 17) / (44 - 17) * 100, 100) * 0.5
    if buffett is not None:
        # Buffett: mean ~90%, peak ~230%+
        score += min((buffett - 90) / (230 - 90) * 100, 100) * 0.5
    return max(0, min(score, 100))


def _gauge_unsustainable_conditions(
    sp_price: float, earnings_yield_pct: float | None, bond_yield_pct: float
) -> float:
    """Gauge 2: Are prices discounting unsustainable conditions?

    Measures the implied equity risk premium — when stocks need
    extreme future earnings growth to justify current prices vs bonds.
    """
    if earnings_yield_pct is None:
        # Fallback: use inverse CAPE if available
        return 50.0
    erp = earnings_yield_pct - bond_yield_pct
    # ERP typically 3-5%. Below 1% = very bubbly. Negative = extreme.
    if erp <= 0:
        return 95.0
    if erp < 1:
        return 80.0
    if erp < 2:
        return 60.0
    if erp < 3:
        return 40.0
    return 20.0


def _gauge_new_buyers(fg_value: float | None) -> float:
    """Gauge 3: How many new buyers have entered the market?

    Proxy: retail sentiment / Fear & Greed skew.
    High F&G + record retail participation = new buyer influx.
    """
    if fg_value is None:
        return 40.0
    # F&G > 75 = extreme greed → lots of new retail. < 25 = fear → no new buyers.
    return min(max((fg_value - 25) / 50 * 100, 0), 100) * 0.7 + 15


def _gauge_bullish_sentiment(fg_value: float | None, rsi: float) -> float:
    """Gauge 4: How broadly bullish is sentiment?"""
    fg_score = 0.0
    if fg_value is not None:
        fg_score = min(max((fg_value - 30) / 45 * 100, 0), 100)
    rsi_score = min(max((rsi - 50) / 30 * 100, 0), 100)
    return fg_score * 0.6 + rsi_score * 0.4


def _gauge_leverage(
    margin_debt_yoy_pct: float | None,
    margin_debt_to_gdp_pct: float | None,
    margin_debt_to_gdp_median: float | None,
) -> float:
    """Gauge 5: Are purchases being financed by high leverage?"""
    score = 50.0  # default moderate
    if margin_debt_yoy_pct is not None:
        # >40% YoY growth = very bubbly, <10% = normal
        growth_score = min(max((margin_debt_yoy_pct - 10) / 40 * 100, 0), 100)
        score = growth_score * 0.5
    if margin_debt_to_gdp_pct is not None and margin_debt_to_gdp_median is not None:
        ratio = margin_debt_to_gdp_pct / margin_debt_to_gdp_median
        # ratio of 2.0 = 100, 1.0 = 0
        gdp_score = min(max((ratio - 1.0) / 1.0 * 100, 0), 100)
        score += gdp_score * 0.5
    return min(score, 100)


def _gauge_forward_purchases(cape: float | None, margin_debt_yoy_pct: float | None) -> float:
    """Gauge 6: Have buyers made extended forward purchases?

    Proxy: corporate capex/AI spending intensity + speculative positioning.
    Uses CAPE as forward-looking price signal and margin growth as proxy.
    """
    score = 50.0
    if cape is not None:
        # High CAPE = market pricing in years of future growth
        score = min(max((cape - 20) / 25 * 100, 0), 100) * 0.6
    if margin_debt_yoy_pct is not None:
        score += min(max((margin_debt_yoy_pct - 5) / 45 * 100, 0), 100) * 0.4
    return min(score, 100)


def compute_bubble_indicator(
    cape: float | None = None,
    buffett: float | None = None,
    sp_price: float = 0,
    bond_yield_pct: float = 4.5,
    fg_value: float | None = None,
    rsi: float = 50.0,
    margin_debt_yoy_pct: float | None = None,
    margin_debt_to_gdp_pct: float | None = None,
    margin_debt_to_gdp_median: float | None = None,
) -> dict:
    """Compute a Dalio-style 6-gauge bubble composite."""
    earnings_yield = round(1 / cape * 100, 2) if cape and cape > 0 else None

    g1 = round(_gauge_prices_vs_traditional(cape, buffett), 1)
    g2 = round(_gauge_unsustainable_conditions(sp_price, earnings_yield, bond_yield_pct), 1)
    g3 = round(_gauge_new_buyers(fg_value), 1)
    g4 = round(_gauge_bullish_sentiment(fg_value, rsi), 1)
    g5 = round(_gauge_leverage(margin_debt_yoy_pct, margin_debt_to_gdp_pct, margin_debt_to_gdp_median), 1)
    g6 = round(_gauge_forward_purchases(cape, margin_debt_yoy_pct), 1)

    composite = round((g1 + g2 + g3 + g4 + g5 + g6) / 6, 1)

    def _reading(score: float) -> str:
        if score >= 80:
            return "Extreme Bubble"
        if score >= 60:
            return "Bubble"
        if score >= 40:
            return "Frothy"
        if score >= 20:
            return "Normal"
        return "Depressed"

    return {
        "composite_score": composite,
        "composite_reading": _reading(composite),
        "gauges": {
            "prices_vs_traditional_measures": {
                "score": g1,
                "reading": _reading(g1),
                "description": "How high are prices relative to traditional measures (CAPE, Buffett Indicator)?",
            },
            "unsustainable_conditions": {
                "score": g2,
                "reading": _reading(g2),
                "description": "Are prices discounting unsustainable conditions (equity risk premium)?",
            },
            "new_buyer_entry": {
                "score": g3,
                "reading": _reading(g3),
                "description": "How many new buyers have entered the market (retail participation proxy)?",
            },
            "bullish_sentiment": {
                "score": g4,
                "reading": _reading(g4),
                "description": "How broadly bullish is sentiment (Fear & Greed, RSI)?",
            },
            "leverage_purchases": {
                "score": g5,
                "reading": _reading(g5),
                "description": "Are purchases being financed by high leverage (margin debt)?",
            },
            "forward_purchases": {
                "score": g6,
                "reading": _reading(g6),
                "description": "Have buyers made extended forward purchases (capex, forward speculation)?",
            },
        },
        "historical_comparisons": {
            "1929_peak": 100,
            "2000_dot_com_peak": 100,
            "2021_meme_stock_era": 73,
            "current": composite,
        },
        "methodology": "Rules-based proxy of Ray Dalio's 6-gauge bubble framework. Each gauge scores 0-100 using CAPE, Buffett Indicator, equity risk premium, Fear & Greed Index, RSI, and margin debt metrics. Composite is equal-weighted average.",
    }
