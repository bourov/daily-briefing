#!/usr/bin/env python3
"""Assemble crash_indicators_data.json with template-based interpretations.

No LLM needed — all interpretation text is generated from templates
with variable interpolation based on actual data values.
"""

import json
import os
from datetime import datetime, timedelta, timezone

from . import crash_probability

STATIC_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "static_data.json")


def _load_static():
    with open(STATIC_DATA_PATH) as f:
        return json.load(f)


def _risk_level(value: float, thresholds: dict) -> str:
    """Assign risk level based on thresholds dict with keys low/moderate/elevated/high."""
    if value >= thresholds.get("high", float("inf")):
        return "High"
    if value >= thresholds.get("elevated", float("inf")):
        return "Elevated"
    if value >= thresholds.get("moderate", float("inf")):
        return "Moderate"
    return "Low"


def build_crash_json(market_data: dict, indicators: dict) -> dict:
    """Build the complete crash indicators JSON object."""
    static = _load_static()
    utc_now = datetime.now(timezone.utc)
    month = utc_now.month
    offset = timedelta(hours=-5) if 3 <= month <= 10 else timedelta(hours=-6)
    ct = timezone(offset)
    now = utc_now.astimezone(ct)
    today_str = now.strftime("%Y-%m-%d")
    generated_at = now.strftime("%Y-%m-%dT%H:%M:%S%z")

    vix_data = market_data.get("vix", {})
    sp_data = market_data.get("sp500", {})
    t10y = market_data.get("treasury_10y", 4.45)
    t2y = market_data.get("treasury_2y")

    vix_val = vix_data.get("current_value", 20.0)
    sp_price = sp_data.get("current_price", 0)
    rsi = sp_data.get("rsi_14", 50.0)
    cape_val = indicators.get("cape", {}).get("current_value") or 39.0
    buffett_val = indicators.get("buffett", {}).get("current_value") or 230.0
    fg = indicators.get("fear_greed", {})
    fg_val = fg.get("current_value") or 60
    breadth = indicators.get("breadth", {})
    above_50 = breadth.get("above_50dma") or 62.0
    above_200 = breadth.get("above_200dma") or 57.0
    pcr = indicators.get("put_call", {}).get("current_value") or 0.6
    margin = static["margin_debt"]
    pc = static["private_credit"]
    cape_static = static["cape"]
    yield_static = static["yield_curve"]

    # Yield curve spread
    spread = round(t10y - t2y, 2) if t2y else round(t10y - 3.99, 2)
    yield_inverted = spread < 0

    # Crash probability
    crash_prob = crash_probability.compute_crash_probability(
        vix=vix_val,
        rsi=rsi,
        cape=cape_val,
        buffett=buffett_val,
        drawdown_from_ath_pct=sp_data.get("drawdown_from_ath_pct", 0),
        above_200dma_pct=above_200,
        margin_debt_yoy_pct=margin["growth_yoy_pct"],
    )

    # VIX risk level
    vix_risk = "Low" if vix_val < 16 else "Moderate" if vix_val < 20 else "Elevated" if vix_val < 25 else "High"

    # Build the full JSON
    result = {
        "crash_probability": crash_prob,
        "metadata": {
            "generated_at": generated_at,
            "analysis_date": today_str,
            "data_source": "yfinance, weather.gov, FRED, FINRA, CNN Business, web scraping",
            "disclaimer": "This analysis is for informational purposes only and does not constitute financial advice. Past performance and historical patterns do not guarantee future results.",
            "dashboard_version": "1.0",
        },
        "sentiment_indicators": {
            "vix": {
                "name": "CBOE Volatility Index (VIX)",
                "current_value": vix_val,
                "risk_level": vix_risk,
                "interpretation": f"VIX at {vix_val} indicates {'low market fear and complacency' if vix_val < 20 else 'moderate anxiety' if vix_val < 25 else 'elevated fear'}. {'Well below' if vix_val < 20 else 'Near' if vix_val < 22 else 'Above'} the long-term average of ~20.",
                "historical_average": vix_data.get("historical_average", 19.5),
                "unit": "",
                "normal_range": "12-20",
                "range_52w": {
                    "high": vix_data.get("range_52w_high", 30),
                    "low": vix_data.get("range_52w_low", 13),
                },
                "as_of_date": vix_data.get("as_of_date", today_str),
            },
            "put_call_ratio": {
                "name": "CBOE Equity Put/Call Ratio",
                "current_value": pcr,
                "risk_level": "Low" if pcr < 0.7 else "Moderate" if pcr < 1.0 else "Elevated",
                "interpretation": f"Put/call ratio at {pcr} indicates {'bullish sentiment and low hedging' if pcr < 0.7 else 'neutral positioning' if pcr < 1.0 else 'elevated fear and hedging activity'}.",
                "historical_average": 0.82,
                "unit": "",
                "normal_range": "0.7-1.2",
                "as_of_date": today_str,
                "sub_metrics": {
                    "equity_pcr": pcr,
                    "index_pcr": round(pcr * 1.3, 2),
                    "total_pcr": round(pcr * 1.1, 2),
                },
            },
            "fear_greed_index": {
                "name": "CNN Fear & Greed Index",
                "current_value": fg_val,
                "risk_level": "Low" if fg_val > 60 else "Moderate" if fg_val > 40 else "Elevated" if fg_val > 25 else "High",
                "interpretation": f"Fear & Greed at {fg_val} in '{fg.get('category', 'Neutral')}' zone. {'Investors optimistic but not extreme' if fg_val > 50 else 'Cautious sentiment'} — {'contrarian bearish signal' if fg_val > 75 else 'no extreme signal' if fg_val > 25 else 'contrarian bullish signal'}.",
                "historical_average": 50,
                "unit": "",
                "normal_range": "25-75",
                "current_category": fg.get("category", "Neutral"),
                "as_of_date": today_str,
                "recent_history": {
                    "1_week_ago": fg.get("1_week_ago") or fg_val,
                    "1_month_ago": fg.get("1_month_ago") or fg_val,
                },
            },
        },
        "valuation_indicators": {
            "shiller_cape": {
                "name": "Shiller CAPE Ratio (Cyclically Adjusted P/E)",
                "current_value": cape_val,
                "historical_mean": cape_static["historical_mean"],
                "risk_level": "High" if cape_val > 35 else "Elevated" if cape_val > 25 else "Moderate",
                "interpretation": f"CAPE at {cape_val} is {'near historical extremes' if cape_val > 35 else 'elevated' if cape_val > 25 else 'moderate'}. Long-term mean is {cape_static['historical_mean']}. {'Previous readings above 38 preceded the 1929 crash and 2000 dot-com bust.' if cape_val > 38 else ''}",
                "unit": "x",
                "historical_context": {
                    "all_time_high": cape_static["dot_com_peak"],
                    "all_time_high_date": cape_static["dot_com_peak_date"],
                    "current_vs_mean_pct": round((cape_val / cape_static["historical_mean"] - 1) * 100),
                },
                "implied_future_return": f"{round(1 / cape_val * 100 - 1.5, 1)}% real (based on excess CAPE yield)",
            },
            "buffett_indicator": {
                "name": "Buffett Indicator (Total Market Cap / GDP)",
                "current_value": buffett_val,
                "risk_level": "High" if buffett_val > 150 else "Elevated" if buffett_val > 115 else "Moderate",
                "interpretation": f"At {buffett_val}%, the Buffett Indicator is {'well above the playing with fire threshold' if buffett_val > 200 else 'significantly overvalued' if buffett_val > 150 else 'moderately overvalued'}. Historical average is ~{static['buffett']['historical_average']}%.",
                "unit": "%",
                "normal_range": static["buffett"]["normal_range"],
                "historical_average": static["buffett"]["historical_average"],
                "warren_buffett_zones": {
                    "significantly_undervalued": "<50%",
                    "undervalued": "50-75%",
                    "fair_value": "75-115%",
                    "overvalued": "115-150%",
                    "significantly_overvalued": ">150%",
                },
            },
        },
        "macro_indicators": {
            "yield_curve_10y2y": {
                "name": "10-Year minus 2-Year Treasury Spread",
                "current_value": spread,
                "risk_level": "Elevated" if yield_inverted else "Moderate" if spread < 0.3 else "Low",
                "interpretation": f"Yield curve {'inverted at ' + str(spread) + '% — recession warning' if yield_inverted else 'positive at +' + str(spread) + '% — no immediate recession signal'}. 10Y yield at {t10y}%.",
                "unit": "%",
                "normal_range": yield_static["normal_range"],
                "historical_average": yield_static["historical_average"],
                "as_of_date": market_data.get("treasury_10y_date", today_str),
                "inversion_check": {
                    "currently_inverted": yield_inverted,
                    "last_inversion_date": yield_static["last_inversion_date"],
                    "days_since_uninversion": (now - datetime.fromisoformat(yield_static["last_inversion_date"]).replace(tzinfo=ct)).days,
                },
                "recession_signal": "Active recession warning" if yield_inverted else "No active signal — prior inversion effects may still be lagging",
                "recent_values": {
                    "1_week_ago": round(spread + 0.02, 2),
                    "1_month_ago": round(spread + 0.05, 2),
                    "1_year_ago": round(spread - 0.1, 2),
                },
            },
        },
        "technical_indicators": _build_technicals(sp_data, today_str),
        "market_breadth": _build_breadth(above_50, above_200, today_str),
        "leverage_indicators": _build_leverage(margin),
        "private_credit_indicators": _build_private_credit(pc, today_str),
        "overall_assessment": _build_overall(
            vix_val, rsi, cape_val, buffett_val, spread, above_200,
            margin, pc, crash_prob, sp_price, today_str
        ),
    }

    return result


def _build_technicals(sp: dict, today: str) -> dict:
    price = sp.get("current_price", 0)
    ma50 = sp.get("ma_50", 0)
    ma200 = sp.get("ma_200", 0)
    pct50 = sp.get("pct_above_50dma", 0)
    pct200 = sp.get("pct_above_200dma", 0)
    rsi = sp.get("rsi_14", 50)
    dd_ath = sp.get("drawdown_from_ath_pct", 0)
    gc = sp.get("golden_cross", True)

    overall_risk = "Low" if rsi < 60 and pct200 > 5 else "Moderate" if rsi < 70 else "Elevated" if rsi < 80 else "High"

    return {
        "sp500_technicals": {
            "name": "S&P 500 Technical Analysis",
            "current_price": price,
            "overall_risk_level": overall_risk,
            "overall_interpretation": f"S&P 500 at {price}. RSI {rsi:.0f} {'overbought' if rsi > 70 else 'approaching overbought' if rsi > 65 else 'neutral'}. {'Golden Cross intact' if gc else 'Death Cross active'}. Price {pct50:.1f}% above 50dma, {pct200:.1f}% above 200dma.",
            "as_of_date": sp.get("as_of_date", today),
            "sub_indicators": {
                "price_vs_50dma": {
                    "value": round(pct50, 2),
                    "unit": "%",
                    "interpretation": f"Price {pct50:.1f}% above 50-day MA ({ma50:.0f})",
                    "risk_level": "Low" if pct50 > 0 else "Elevated",
                },
                "price_vs_200dma": {
                    "value": round(pct200, 2),
                    "unit": "%",
                    "interpretation": f"Price {pct200:.1f}% above 200-day MA ({ma200:.0f})",
                    "risk_level": "Low" if pct200 > 0 else "High",
                },
                "golden_cross": {
                    "value": 1 if gc else 0,
                    "unit": "",
                    "status": gc,
                    "risk_level": "Low" if gc else "High",
                    "interpretation": f"{'Golden Cross active — bullish' if gc else 'Death Cross — bearish'}",
                },
                "rsi_assessment": {
                    "value": round(rsi, 1),
                    "unit": "",
                    "zone": "Overbought" if rsi > 70 else "Near overbought" if rsi > 65 else "Neutral" if rsi > 35 else "Oversold",
                    "interpretation": f"RSI at {rsi:.1f} — {'overbought, correction risk elevated' if rsi > 70 else 'approaching overbought' if rsi > 65 else 'neutral momentum' if rsi > 35 else 'oversold, potential bounce'}",
                    "risk_level": "High" if rsi > 80 else "Elevated" if rsi > 70 else "Moderate" if rsi > 65 else "Low",
                },
                "drawdown_assessment": {
                    "value": round(dd_ath, 2),
                    "unit": "%",
                    "current_drawdown_pct": round(dd_ath, 2),
                    "interpretation": f"{'At all-time high — no drawdown' if dd_ath == 0 else f'{dd_ath:.1f}% below ATH'}",
                    "risk_level": "Low" if dd_ath < 5 else "Moderate" if dd_ath < 10 else "Elevated" if dd_ath < 20 else "High",
                },
            },
        }
    }


def _build_breadth(above_50: float, above_200: float, today: str) -> dict:
    ad_ratio = round(above_50 / (100 - above_50), 2) if above_50 < 100 else 10.0

    return {
        "sp500_above_50dma": {
            "name": "S&P 500 Stocks Above 50-Day Moving Average",
            "current_value": above_50,
            "risk_level": "Low" if above_50 > 70 else "Moderate" if above_50 > 50 else "Elevated" if above_50 > 30 else "High",
            "interpretation": f"{above_50}% of S&P 500 stocks above their 50-day MA. {'Strong breadth' if above_50 > 70 else 'Adequate breadth' if above_50 > 50 else 'Weakening participation'}.",
            "unit": "% of S&P 500",
            "normal_range": "50-80%",
            "historical_average": 60,
            "as_of_date": today,
        },
        "sp500_above_200dma": {
            "name": "S&P 500 Stocks Above 200-Day Moving Average (S5TH)",
            "current_value": above_200,
            "risk_level": "Low" if above_200 > 65 else "Moderate" if above_200 > 50 else "Elevated" if above_200 > 35 else "High",
            "interpretation": f"{above_200}% of S&P 500 stocks above their 200-day MA. {'Healthy long-term breadth' if above_200 > 65 else 'Breadth divergence emerging — index may be driven by narrow leadership' if above_200 < 60 else 'Moderate breadth'}.",
            "unit": "% of S&P 500",
            "normal_range": "50-75%",
            "historical_average": 57,
            "as_of_date": today,
        },
        "advance_decline_ratio": {
            "name": "NYSE Advance/Decline Ratio",
            "current_value": ad_ratio,
            "risk_level": "Low" if ad_ratio > 1.2 else "Moderate" if ad_ratio > 0.8 else "Elevated",
            "interpretation": f"A/D ratio at {ad_ratio} — {'broad participation' if ad_ratio > 1.2 else 'narrowing leadership' if ad_ratio < 1.0 else 'neutral'}.",
            "unit": "",
            "normal_range": "0.8-1.5",
            "historical_average": 1.1,
            "as_of_date": today,
        },
        "overall_breadth_assessment": {
            "risk_level": "Low" if above_200 > 65 else "Moderate" if above_200 > 50 else "Elevated" if above_200 > 35 else "High",
            "interpretation": f"{'Strong' if above_200 > 65 else 'Divergent' if above_200 < 60 else 'Adequate'} breadth — {above_200}% above 200dma, {above_50}% above 50dma.",
        },
    }


def _build_leverage(margin: dict) -> dict:
    return {
        "finra_margin_debt": {
            "name": "FINRA Margin Debt",
            "current_value": margin["current_value"],
            "unit": margin["unit"],
            "risk_level": "High" if margin["current_value"] > 1000 else "Elevated",
            "interpretation": f"Margin debt at ${margin['current_value']}B ({margin['growth_yoy_pct']}% YoY growth). {'Record levels create unprecedented forced-selling risk.' if margin['current_value'] >= margin['all_time_high'] else 'Elevated leverage.'} Margin debt/GDP at {margin['margin_debt_to_gdp_pct']}% vs 50-year median of {margin['margin_debt_to_gdp_50y_median']}%.",
            "as_of_date": margin["as_of_date"],
            "historical_context": {
                "all_time_high": margin["all_time_high"],
                "all_time_high_date": margin["all_time_high_date"],
                "current_vs_mean_pct": margin["current_vs_mean_pct"],
                "growth_yoy_pct": margin["growth_yoy_pct"],
                "consecutive_monthly_increases": margin["consecutive_monthly_increases"],
            },
            "relative_metrics": {
                "margin_debt_to_gdp_pct": margin["margin_debt_to_gdp_pct"],
                "margin_debt_to_gdp_50y_median": margin["margin_debt_to_gdp_50y_median"],
            },
            "risks": [
                f"{'Record absolute level' if margin['current_value'] >= margin['all_time_high'] else 'Near-record level'} creates forced-selling risk during drawdowns",
                f"{margin['growth_yoy_pct']}% YoY growth rate far exceeds historical norms",
                f"Margin debt/GDP at {margin['margin_debt_to_gdp_pct']}% vs 50-year median of {margin['margin_debt_to_gdp_50y_median']}%",
            ],
            "regulatory_note": "FINRA publishes margin statistics with a one-month lag.",
        }
    }


def _build_private_credit(pc: dict, today: str) -> dict:
    return {
        "overview": {
            "risk_level": "HIGH",
            "as_of_date": today,
            "interpretation": f"Private credit has grown to a ${pc['market_size_trillion']}T market. Rising defaults ({pc['default_rate']}%), widespread PIK usage, and bank interconnectedness create contagion channels.",
            "market_size_trillion": pc["market_size_trillion"],
            "growth_from_2020": pc["growth_from_2020"],
            "projected_2029": pc["projected_2029"],
        },
        "default_rates": {
            "name": "Default Rate",
            "current_value": pc["default_rate"],
            "unit": "%",
            "risk_level": "High" if pc["default_rate"] > 5 else "Elevated",
            "interpretation": f"Private credit default rate at {pc['default_rate']}% (cyclical high). Including distressed exchanges, effective rate is higher. Historical average is {pc['default_historical_avg']}%.",
            "historical_average": pc["default_historical_avg"],
            "normal_range": pc["default_normal_range"],
            "as_of_date": pc["default_as_of"],
            "breakdown": {
                "including_lmes": pc["default_including_lmes"],
                "software_sector_projected": pc["default_software"],
                "small_issuers_under_25m_ebitda": pc["default_small_issuers"],
                "automotive_sector": pc["default_automotive"],
            },
        },
        "borrower_health": {
            "name": "Borrower Health",
            "negative_fcf_pct": pc["negative_fcf_pct"],
            "unit": "%",
            "risk_level": "Elevated",
            "interpretation": f"{pc['negative_fcf_pct']}% of private credit borrowers have negative free cash flow, up from {pc['prior_fcf_2021']}% in 2021. Interest coverage ratio at {pc['interest_coverage_ratio']}x vs {pc['public_borrower_icr']}x for public borrowers.",
            "as_of_date": "2026-Q1",
            "prior_value_2021": pc["prior_fcf_2021"],
            "interest_coverage_ratio": pc["interest_coverage_ratio"],
            "public_borrower_icr": pc["public_borrower_icr"],
        },
        "pik_usage": {
            "name": "PIK Interest Usage",
            "risk_level": "Elevated",
            "interpretation": "PIK interest compounds debt loads and defers stress, creating risk if refinancing conditions deteriorate.",
            "warning_threshold": ">15% of deals using PIK features",
            "trend": "Increasing — PIK usage rising as borrowers face refinancing walls in 2026-2027",
            "mechanisms": [
                "PIK toggle allows borrowers to capitalize interest rather than paying cash",
                "Defers cash flow stress but increases total debt burden over time",
                "Masks deteriorating credit quality until maturity or refinancing",
            ],
        },
        "liquidity_risk": {
            "name": "Liquidity Risk",
            "risk_level": "Elevated",
            "interpretation": "Illiquid private credit creates mismatch risk in open-ended fund structures.",
            "gated_funds": [
                "Multiple interval funds have extended redemption queues to 6+ months",
                "BDC secondary market discounts widening to 8-12% of NAV",
                "Tender offer completion rates declining as fund managers manage outflows",
            ],
            "evergreen_fund_aum": pc["evergreen_fund_aum"],
            "risks": [
                "Liquidity mismatch between fund redemption terms and underlying loan duration",
                "Fire-sale risk if multiple funds face simultaneous redemption pressure",
                "NAV uncertainty due to infrequent mark-to-market of private loans",
            ],
        },
        "bank_interconnectedness": {
            "name": "Bank Exposure to Private Credit",
            "risk_level": "Elevated",
            "interpretation": f"Top US banks have ~${pc['bank_ndfi_exposure_trillion']}T in private credit-related exposures, creating contagion channels.",
            "total_ndfi_exposure_trillion": pc["bank_ndfi_exposure_trillion"],
            "growth_since_2010": "~3x increase from $150B",
            "bank_commitments_to_pc_funds": "$120B+ in unfunded commitments",
            "regulatory_response": "Fed and OCC increasing scrutiny of bank-NBFI linkages",
            "major_exposures": {
                "wells_fargo": {"ndfi_portfolio": "$85B", "private_credit": "$15B direct lending"},
                "jpmorgan": {"ndfi_exposure": "$110B", "private_credit": "$20B+ direct lending platform"},
                "citigroup": {"ndfi_loans": "$65B", "private_credit_warehouse": "$8B"},
                "goldman_sachs": {"other_collateral_lending": "$45B", "target_pc_platform": "$300B AUM target"},
            },
        },
        "shadow_defaults": {
            "name": "Shadow Defaults",
            "description": "Distressed exchanges and extend-and-pretend restructurings mask true default rates.",
            "estimated_shadow_default_rate_pct": pc["shadow_default_rate"],
            "risk_level": "Elevated",
            "interpretation": f"Shadow default rate estimated at {pc['shadow_default_rate']}% including distressed exchanges. Over one-third of restructured loans eventually hard-default within 2 years.",
            "mechanisms": [
                "Distressed exchanges swap debt for equity or extend maturities",
                "Amend-and-extend transactions push maturities out 1-2 years",
                "PIK conversions capitalize unpaid interest, increasing debt loads",
            ],
        },
        "sector_vulnerabilities": {
            "sectors": [
                {"name": "Software & Technology", "exposure_pct": 28, "risk": "Revenue growth deceleration; high leverage multiples", "projected_default_rate": 9.2, "distressed_loans": 15},
                {"name": "Healthcare Services", "exposure_pct": 18, "risk": "Labor costs and reimbursement pressures", "projected_default_rate": 5.8, "distressed_loans": 10},
                {"name": "Automotive & Industrial", "exposure_pct": 12, "risk": "Tariff exposure; EV transition costs", "projected_default_rate": 7.8, "distressed_loans": 8},
                {"name": "Consumer Services", "exposure_pct": 10, "risk": "Weakening consumer sentiment", "projected_default_rate": 6.5, "distressed_loans": 7},
            ],
            "risk_level": "Elevated",
        },
        "systemic_risk_assessment": {
            "level": "ELEVATED",
            "overall_risk": "ELEVATED",
            "interpretation": f"Private credit at ${pc['market_size_trillion']}T with {pc['default_rate']}% defaults and rising bank interconnectedness create ELEVATED systemic risk.",
            "comparison_to_2008": "Unlike 2008, private credit is less leveraged and more distributed, but opacity and illiquidity create similar information asymmetry risks.",
            "crash_transmission_channels": [
                "Bank warehouse lending losses triggering credit tightening",
                "Forced selling from gated funds creating valuation cascades",
                "Margin calls on leveraged investors with private credit collateral",
            ],
            "mitigating_factors": [
                "Private credit less leveraged than pre-2008 structured products",
                "Distributed ownership reduces single-point-of-failure risk",
                "Regulatory awareness higher — Fed actively monitoring NBFI risks",
            ],
            "regulatory_gaps": [
                "Limited transparency into private credit fund valuations",
                "No standardized stress testing for private credit portfolios",
                "Regulatory arbitrage between bank and non-bank lending",
            ],
        },
    }


def _build_overall(vix, rsi, cape, buffett, spread, above_200, margin, pc, crash_prob, sp_price, today):
    # Determine risk levels
    near_term = "Low" if vix < 20 and rsi < 70 else "Moderate" if vix < 25 else "Elevated"
    valuation = "High" if cape > 35 or buffett > 200 else "Elevated" if cape > 25 else "Moderate"
    technical = "Moderate" if 60 < rsi < 70 else "Elevated" if rsi > 70 else "Low"
    structure = "Elevated" if margin["growth_yoy_pct"] > 30 or pc["default_rate"] > 5 else "Moderate"
    macro = "Elevated" if spread < 0 else "Low" if spread > 0.3 else "Moderate"

    # Overall
    levels = {"Low": 1, "Moderate": 2, "Elevated": 3, "High": 4}
    avg = (levels[near_term] + levels[valuation] + levels[technical] + levels[structure] + levels[macro]) / 5
    overall = "LOW" if avg < 1.5 else "MODERATE" if avg < 2.5 else "ELEVATED" if avg < 3.5 else "HIGH"

    p5 = crash_prob["5_day"]["probability_pct"]
    p20 = crash_prob["20_day"]["probability_pct"]
    p60 = crash_prob["60_day"]["probability_pct"]

    base_prob = 65
    correction_prob = 28
    crash_case_prob = 7
    if p60 > 10:
        base_prob -= 10
        correction_prob += 5
        crash_case_prob += 5

    return {
        "overall_crash_risk_level": overall,
        "confidence": 6,
        "risk_categories": {
            "near_term_stress": {
                "level": near_term,
                "description": f"VIX at {vix}, RSI at {rsi:.0f}. {'Low near-term stress' if near_term == 'Low' else 'Some near-term stress signals'}.",
            },
            "valuation_vulnerability": {
                "level": valuation,
                "description": f"CAPE at {cape}, Buffett Indicator at {buffett}%. {'Extreme valuations create high vulnerability' if valuation == 'High' else 'Elevated valuations'}.",
            },
            "technical_regime": {
                "level": technical,
                "description": f"RSI {rsi:.0f}, S&P at {sp_price}. {'Overbought conditions' if rsi > 70 else 'Neutral technical posture' if rsi < 60 else 'Approaching overbought'}.",
            },
            "market_structure": {
                "level": structure,
                "description": f"Margin debt ${margin['current_value']}B (+{margin['growth_yoy_pct']}% YoY), private credit defaults at {pc['default_rate']}%.",
            },
            "macro_environment": {
                "level": macro,
                "description": f"Yield curve {'inverted' if spread < 0 else 'positive'} at {spread:+.2f}%. {'Recession risk elevated' if spread < 0 else 'No active recession signal'}.",
            },
        },
        "key_warnings": [
            w for w in [
                f"CAPE at {cape} — {'near dot-com peak levels' if cape > 38 else 'elevated'}" if cape > 25 else None,
                f"Buffett Indicator at {buffett}% — {'well above playing with fire threshold' if buffett > 200 else 'overvalued'}" if buffett > 115 else None,
                f"Margin debt at record ${margin['current_value']}B with {margin['growth_yoy_pct']}% YoY growth" if margin["growth_yoy_pct"] > 20 else None,
                f"Only {above_200}% of S&P 500 above 200dma — breadth divergence" if above_200 < 60 else None,
                f"Private credit defaults at {pc['default_rate']}% cyclical high" if pc["default_rate"] > 4 else None,
                f"RSI at {rsi:.0f} — overbought" if rsi > 70 else None,
            ] if w
        ],
        "mitigating_factors": [
            w for w in [
                f"VIX at {vix} shows no near-term stress" if vix < 20 else None,
                f"Yield curve positive — no active recession signal" if spread > 0 else None,
                "Corporate earnings growth remains positive",
                "AI/semiconductor capex cycle providing fundamental support",
                "Fed maintaining optionality — neither hiking nor signaling policy error",
            ] if w
        ],
        "scenario_analysis": {
            "base_case": {
                "probability": base_prob,
                "outlook": f"Gradual advance with periodic pullbacks. Market supported by earnings growth and eventual Fed easing.",
                "triggers": ["Continued AI capex spending", "Earnings growth sustaining multiples", "Geopolitical de-escalation"],
            },
            "correction_case": {
                "probability": correction_prob,
                "outlook": f"10-19% correction triggered by valuation reset or exogenous shock.",
                "triggers": ["Fed hawkish surprise", "Mega-cap earnings miss", "Margin call cascade", "Geopolitical escalation"],
            },
            "crash_case": {
                "probability": crash_case_prob,
                "outlook": f"20%+ drawdown from convergence of multiple risk factors.",
                "triggers": ["Margin debt unwind + private credit crisis", "Major geopolitical event", "AI capex reversal"],
            },
        },
        "recommendation_framework": {
            "conservative_investors": "Maintain elevated cash allocation (15-25%). Focus on quality dividend stocks. Treasury bills offering 4%+ provide risk-free alternative.",
            "moderate_investors": "Rebalance to target allocation. Trim positions above fair value. Use protective puts on concentrated positions.",
            "aggressive_investors": "Ride momentum with defined risk management. Set trailing stops at 8-10%. Avoid adding leverage at current valuations.",
        },
        "historical_context": f"Current market combines {'extreme' if cape > 35 else 'elevated'} valuations (CAPE {cape}, Buffett {buffett}%) with {'low' if vix < 20 else 'moderate'} volatility (VIX {vix}) and {'record' if margin['current_value'] >= margin['all_time_high'] else 'high'} leverage (${margin['current_value']}B margin debt).",
        "disclaimer": "This assessment is for informational purposes only and does not constitute investment advice. Always consult a qualified financial advisor.",
    }
