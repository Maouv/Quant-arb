#!/usr/bin/env python3
"""Download 4h interval coins FR data separately from 8h universe.
Data range: 2022-01 to 2026-04
"""
import os
import requests
import zipfile
import pandas as pd
from io import BytesIO
from datetime import datetime, timezone

# 4h coins that have spot + futures
COINS_4H = [
    'ONDOUSDT', 'TAOUSDT', 'TONUSDT', 'ENAUSDT', 'PENGUUSDT',
    'JTOUSDT', 'FIDAUSDT', 'EDENUSDT', 'ASTERUSDT'
]

BASE_URL = "https://data.binance.vision/data/futures/um/monthly/fundingRate/{symbol}/{symbol}-fundingRate-{year}-{month:02d}.zip"
OUT_DIR = "./funding_rate_data_4h"

def download_coin(symbol):
    """Download all available monthly data for a coin"""
    os.makedirs(OUT_DIR, exist_ok=True)
    all_data = []
    
    for year in range(2022, 2027):  # 2022-2026
        for month in range(1, 13):
            if year == 2026 and month > 4:  # Stop at April 2026
                break
            url = BASE_URL.format(symbol=symbol, year=year, month=month)
            try:
                resp = requests.get(url, timeout=30)
                if resp.status_code == 200:
                    with zipfile.ZipFile(BytesIO(resp.content)) as zf:
                        for name in zf.namelist():
                            if name.endswith('.csv'):
                                with zf.open(name) as f:
                                    df = pd.read_csv(f)
                                    all_data.append(df)
                else:
                    pass  # Silently skip missing months
            except Exception as e:
                print(f"    Error {year}-{month:02d}: {e}")
    
    if all_data:
        merged = pd.concat(all_data, ignore_index=True)
        merged = merged.sort_values('calc_time').reset_index(drop=True)
        merged.to_csv(f"{OUT_DIR}/{symbol}-fundingRate.csv", index=False)
        return merged
    return None

def verify_interval(df):
    """Verify actual funding interval from data"""
    if len(df) < 2:
        return None
    diff = df['calc_time'].iloc[1] - df['calc_time'].iloc[0]
    hours = diff / (1000 * 3600)
    return hours

def main():
    print("=" * 60)
    print("DOWNLOADING 4H INTERVAL COINS")
    print("Period: 2022-01 to 2026-04")
    print("=" * 60)
    
    results = []
    
    for coin in COINS_4H:
        print(f"\n{coin}:")
        df = download_coin(coin)
        
        if df is None or len(df) == 0:
            print("  No data found")
            continue
        
        # Stats
        first_ts = df['calc_time'].iloc[0]
        last_ts = df['calc_time'].iloc[-1]
        first = datetime.fromtimestamp(first_ts/1000, tz=timezone.utc).strftime('%Y-%m-%d')
        last = datetime.fromtimestamp(last_ts/1000, tz=timezone.utc).strftime('%Y-%m-%d')
        
        interval = verify_interval(df)
        
        print(f"  Rows: {len(df)}")
        print(f"  Range: {first} → {last}")
        print(f"  Interval: {interval:.0f}h" if interval else "  Interval: N/A")
        
        results.append({
            'symbol': coin,
            'rows': len(df),
            'first': first,
            'last': last,
            'interval': interval
        })
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'Symbol':<14} {'Rows':>8} {'Interval':>8} {'Range'}")
    print("-" * 60)
    for r in results:
        print(f"{r['symbol']:<14} {r['rows']:>8} {r['interval']:>7.0f}h  {r['first']} → {r['last']}")
    
    # Check which coins have enough data (>= 12 months = ~365 settlements for 4h)
    print("\n" + "=" * 60)
    print("DATA ADEQUACY (need >= 12 months for Phase 1)")
    print("=" * 60)
    for r in results:
        if r['rows'] >= 365:
            print(f"{r['symbol']:<14} ✅ OK ({r['rows']} rows)")
        else:
            print(f"{r['symbol']:<14} ⚠️  INSUFFICIENT ({r['rows']} rows, need ~365+)")

if __name__ == "__main__":
    main()
