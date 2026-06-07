#!/usr/bin/env python3
"""Fetch market data from Yahoo Finance.

Reuses logic from bourov.github.io/scripts/update_crash_data.py.
"""

import sys

import yfinance as yf


def fetch_market_data() -> dict:
    """Fetch VIX, S&P 500, and Treasury yield data from Yahoo Finance."""
    data = {}

    # --- VIX ---
    try:
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="1y")
        if not hist.empty:
            data["vix"] = {
                "current_value": round(float(hist["Close"].iloc[-1]), 2),
                "as_of_date": hist.index[-1].strftime("%Y-%m-%d"),
                "range_52w_low": round(float(hist["Close"].min()), 2),
                "range_52w_high": round(float(hist["Close"].max()), 2),
                "historical_average": 19.5,
            }
    except Exception as exc:
        print(f"Warning: VIX fetch failed: {exc}", file=sys.stderr)

    # --- S&P 500 ---
    try:
        sp = yf.Ticker("^GSPC")
        hist = sp.history(period="2y")
        if not hist.empty:
            close = hist["Close"]
            price = float(close.iloc[-1])
            ma50 = float(close.rolling(50).mean().iloc[-1])
            ma200 = float(close.rolling(200).mean().iloc[-1])

            # RSI-14
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0).rolling(14).mean().iloc[-1]
            loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean().iloc[-1]
            rsi = 100.0 - (100.0 / (1.0 + float(gain) / float(loss))) if loss else 100.0

            high_52w = float(close[-252:].max()) if len(close) >= 252 else float(close.max())
            ath = float(close.max())

            # Golden cross: 50dma > 200dma
            golden_cross = ma50 > ma200

            data["sp500"] = {
                "current_price": round(price, 2),
                "as_of_date": hist.index[-1].strftime("%Y-%m-%d"),
                "ma_50": round(ma50, 2),
                "ma_200": round(ma200, 2),
                "pct_above_50dma": round((price / ma50 - 1) * 100, 2),
                "pct_above_200dma": round((price / ma200 - 1) * 100, 2),
                "rsi_14": round(rsi, 2),
                "high_52w": round(high_52w, 2),
                "ath": round(ath, 2),
                "ath_date": hist.index[close.values.argmax()].strftime("%Y-%m-%d"),
                "drawdown_from_52w_high_pct": round((1 - price / high_52w) * 100, 2),
                "drawdown_from_ath_pct": round((1 - price / ath) * 100, 2),
                "golden_cross": golden_cross,
            }
    except Exception as exc:
        print(f"Warning: S&P 500 fetch failed: {exc}", file=sys.stderr)

    # --- 10Y Treasury yield ---
    try:
        tnx = yf.Ticker("^TNX")
        h10 = tnx.history(period="5d")
        if not h10.empty:
            data["treasury_10y"] = round(float(h10["Close"].iloc[-1]), 3)
            data["treasury_10y_date"] = h10.index[-1].strftime("%Y-%m-%d")
    except Exception as exc:
        print(f"Warning: 10Y yield fetch failed: {exc}", file=sys.stderr)

    # --- 2Y Treasury yield ---
    try:
        twy = yf.Ticker("^IRX")  # 13-week T-bill as proxy; or use 2YY=F
        h2 = twy.history(period="5d")
        if not h2.empty:
            data["treasury_2y"] = round(float(h2["Close"].iloc[-1]), 3)
    except Exception as exc:
        print(f"Warning: 2Y yield fetch failed: {exc}", file=sys.stderr)

    # --- 2Y Treasury yield (direct) ---
    try:
        twy = yf.Ticker("2YY=F")
        h2 = twy.history(period="5d")
        if not h2.empty:
            data["treasury_2y"] = round(float(h2["Close"].iloc[-1]), 3)
    except Exception:
        pass  # fallback already attempted above

    return data
