#!/usr/bin/env python3
"""Download funding rate data - v2
Adds 2025 Jun-Dec and 2026 Jan-Apr to existing data
"""
import os
import requests
import zipfile
import pandas as pd
from io import BytesIO

# Universe only (excluded ONDO, TAO - 4h interval)
COINS = ['ETHUSDT', 'XRPUSDT', 'DOGEUSDT', 'SUIUSDT', 'ADAUSDT', 
         'LINKUSDT', 'UNIUSDT', 'ZECUSDT', 'INJUSDT', 'NEARUSDT', 
         'AAVEUSDT']

BASE_URL = "https://data.binance.vision/data/futures/um/monthly/fundingRate/{symbol}/{symbol}-fundingRate-{year}-{month:02d}.zip"
OUT_DIR = "./funding_rate_data"

def download_new_months(symbol, new_months):
    """Download only new months and append to existing file"""
    all_data = []
    existing_file = f"{OUT_DIR}/{symbol}-fundingRate.csv"
    
    # Load existing data
    if os.path.exists(existing_file):
        existing_df = pd.read_csv(existing_file)
        print(f"  Existing: {len(existing_df)} records")
    else:
        existing_df = pd.DataFrame()
        print(f"  No existing file, will create new")
    
    # Download new months
    for year, month in new_months:
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
                print(f"    {year}-{month:02d}: OK ({len(df)} records)")
            else:
                print(f"    {year}-{month:02d}: Not found (status {resp.status_code})")
        except Exception as e:
            print(f"    {year}-{month:02d}: Error - {e}")
    
    if all_data:
        new_df = pd.concat(all_data, ignore_index=True)
        
        # Merge with existing
        if not existing_df.empty:
            merged = pd.concat([existing_df, new_df], ignore_index=True)
            # Remove duplicates by calc_time
            merged = merged.drop_duplicates(subset=['calc_time'], keep='last')
            merged = merged.sort_values('calc_time').reset_index(drop=True)
        else:
            merged = new_df
        
        merged.to_csv(existing_file, index=False)
        print(f"  Final: {len(merged)} records")
        return merged
    
    return existing_df

def main():
    # New months to download: 2025 Jun-Dec, 2026 Jan-Apr
    new_months = [
        (2025, 6), (2025, 7), (2025, 8), (2025, 9), (2025, 10), (2025, 11), (2025, 12),
        (2026, 1), (2026, 2), (2026, 3), (2026, 4)
    ]
    
    print("="*60)
    print("DOWNLOADING NEW FUNDING RATE DATA")
    print("Period: 2025-06 to 2026-04")
    print("="*60)
    
    for coin in COINS:
        print(f"\n{coin}:")
        download_new_months(coin, new_months)
    
    print("\n" + "="*60)
    print("DONE")
    print("="*60)

if __name__ == "__main__":
    main()
