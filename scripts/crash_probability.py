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
