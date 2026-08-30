#!/usr/bin/env python3
"""Total return (dividends reinvested) over trailing windows for the
research-2026-08 stock universe, vs benchmarks.

Method: yfinance auto-adjusted closes. Yahoo's adjusted close back-adjusts for
both splits and cash dividends, which is equivalent to reinvesting each dividend
at the close on its ex-date. Return = P_adj(end)/P_adj(start) - 1.

Usage:
  python3 tools/total_returns.py                 # default universe + SPY/QQQ/XBI
  python3 tools/total_returns.py NVDA MU GOOG    # explicit tickers
  python3 tools/total_returns.py --csv out.csv
"""
import argparse
import sys
from datetime import date

import pandas as pd
import yfinance as yf

# research-2026-08/ tickers. SPCX (SpaceX) is private -> no market data.
UNIVERSE = ["ALNY", "COHR", "DHR", "GOOG", "LITE", "MRNA", "MRVI",
            "MU", "NTLA", "NVDA", "PLTR", "SNDK", "TSLA"]
# Comparison names requested alongside the research universe.
COMPARISON = ["META", "KO", "AXP"]
BENCHMARKS = ["SPY", "QQQ", "XBI"]
WINDOWS = [("10Y", 10), ("5Y", 5), ("3Y", 3), ("1Y", 1)]


def fetch(tickers, years=11):
    """Split- and dividend-adjusted daily closes."""
    df = yf.download(tickers, period=f"{years}y", auto_adjust=True,
                     progress=False, actions=False)["Close"]
    if isinstance(df, pd.Series):
        df = df.to_frame(tickers[0])
    return df.dropna(how="all")


def window_return(s, years):
    """Total return + CAGR over the trailing `years`, or None if history is short."""
    s = s.dropna()
    if s.empty:
        return None
    end = s.index[-1]
    start = end - pd.DateOffset(years=years)
    if s.index[0] > start + pd.Timedelta(days=10):   # not enough history
        return None
    sub = s.loc[:start]
    if sub.empty:
        return None
    p0, p1 = sub.iloc[-1], s.iloc[-1]
    tr = p1 / p0 - 1.0
    yrs = (end - sub.index[-1]).days / 365.25
    return {"start": sub.index[-1].date(), "total_return": tr,
            "cagr": (1 + tr) ** (1 / yrs) - 1, "mult": p1 / p0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="*", default=None)
    ap.add_argument("--csv")
    ap.add_argument("--no-benchmarks", action="store_true")
    args = ap.parse_args()

    tickers = args.tickers or (UNIVERSE + COMPARISON)
    if not args.no_benchmarks:
        tickers = tickers + [b for b in BENCHMARKS if b not in tickers]

    px = fetch(tickers)
    asof = px.index[-1].date()

    rows = []
    for t in tickers:
        if t not in px.columns:
            print(f"  !! no data for {t}", file=sys.stderr)
            continue
        row = {"ticker": t, "first_date": px[t].dropna().index[0].date()}
        for label, yrs in WINDOWS:
            r = window_return(px[t], yrs)
            row[f"{label}_total"] = r["total_return"] if r else None
            row[f"{label}_cagr"] = r["cagr"] if r else None
        rows.append(row)

    out = pd.DataFrame(rows).set_index("ticker")

    def pct(x):
        return "     n/a" if pd.isna(x) else f"{x*100:>7.1f}%"

    print(f"\nTotal return, dividends reinvested (adj. close) — as of {asof}\n")
    hdr = f"{'ticker':<7}{'since':<12}" + "".join(
        f"{l+' tot':>10}{l+' cagr':>11}" for l, _ in WINDOWS)
    print(hdr)
    print("-" * len(hdr))
    for t, r in out.iterrows():
        line = f"{t:<7}{str(r['first_date']):<12}"
        for label, _ in WINDOWS:
            line += f"{pct(r[f'{label}_total']):>10}{pct(r[f'{label}_cagr']):>11}"
        print(line)
    print("\nn/a = the ticker did not trade for the full window "
          "(IPO/spin-off inside the period).")

    if args.csv:
        out.to_csv(args.csv)
        print(f"\nwrote {args.csv}")


if __name__ == "__main__":
    main()
