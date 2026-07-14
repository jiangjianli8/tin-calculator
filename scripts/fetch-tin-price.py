#!/usr/bin/env python3
"""Fetch tin price — SMM spot (primary) + SHFE futures (fallback).
   Copper calculator uses same dual-source strategy.
   Saves to data/price.json for GitHub Pages.
"""
import json, os, re, sys
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
now = datetime.now(CST)


def fetch_smm_spot():
    """Try to fetch SMM 1# tin spot price via AKShare futures_spot.
       Returns price_dict or None on failure.
    """
    try:
        import akshare as ak
        # AKShare's spot price from SMM; symbol may vary by version
        df = ak.futures_spot_price(symbol="锡", market="smm")
        if df is not None and not df.empty:
            # Returns DataFrame with spot price data
            row = df.iloc[0] if len(df) > 0 else None
            if row is not None:
                price_val = 0
                for col in ["average", "price", "spot_price", "均价"]:
                    if col in df.columns:
                        price_val = float(row[col]) if row[col] else 0
                        if price_val > 0:
                            break
                if price_val > 0:
                    return {
                        "symbol": "SMM 1#电解锡（现货）— 上海有色网",
                        "price": round(price_val),
                        "unit": "元/吨",
                        "date": str(row.get("date", "")),
                        "updated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "source": "akshare_smm_spot",
                    }
    except Exception:
        pass  # Fall through to futures
    return None


def fetch_shfe_futures():
    """Fetch SHFE tin futures (SN0) via AKShare — tracks SMM spot closely.
       SHFE tin settlement price is the industry benchmark, typically
       within 0.5% of SMM 1# spot price.
    """
    try:
        import akshare as ak
    except ImportError:
        print("ERROR: akshare not installed. Run: pip install akshare")
        sys.exit(1)

    df = ak.futures_zh_daily_sina(symbol="SN0")

    if df.empty:
        print("WARN: No data returned from AKShare for SN0")
        return None

    latest = df.iloc[-1]
    settle_price = float(latest.get("settle", 0))
    close_price = float(latest.get("close", 0))
    price = settle_price if settle_price > 0 else close_price

    result = {
        "symbol": "SMM 1#电解锡（现货参考·SHFE结算价）",
        "price": round(price),
        "unit": "元/吨",
        "date": str(latest.get("date", "")),
        "updated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "akshare_sina_futures",
        "detail": {
            "open": float(latest.get("open", 0)),
            "high": float(latest.get("high", 0)),
            "low": float(latest.get("low", 0)),
            "close": close_price,
            "settle": settle_price,
            "volume": int(latest.get("volume", 0)),
            "hold": int(latest.get("hold", 0)),
        }
    }

    if len(df) >= 2:
        prev = df.iloc[-2]
        prev_settle = float(prev.get("settle", 0))
        if prev_settle > 0 and settle_price > 0:
            change = settle_price - prev_settle
            change_pct = (change / prev_settle) * 100
            result["change"] = round(change)
            result["change_rate"] = round(change_pct, 2)
            result["trend"] = "up" if change > 0 else ("down" if change < 0 else "flat")

    return result


def fetch_price():
    """Fetch tin price — try SMM spot first, fall back to SHFE futures."""
    # Try SMM spot first
    result = fetch_smm_spot()
    if result and result.get("price", 0) > 0:
        print("Using SMM spot price")
        return result

    # Fall back to SHFE futures
    print("Falling back to SHFE futures (SN0)")
    return fetch_shfe_futures()


def main():
    price_data = fetch_price()

    if not price_data:
        print("ERROR: Failed to fetch tin price data")
        sys.exit(1)

    out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "price.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(price_data, f, ensure_ascii=False, indent=2)

    print(f"Tin Price: {price_data['price']:,} 元/吨")
    print(f"Date: {price_data['date']}")
    if "change" in price_data:
        sign = "+" if price_data["change"] > 0 else ""
        print(f"Change: {sign}{price_data['change']:,} ({sign}{price_data['change_rate']}%)")
    print(f"Source: {price_data['source']}")
    print(f"Saved to: {out_path}")


if __name__ == "__main__":
    main()
