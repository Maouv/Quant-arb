#!/usr/bin/env python3
"""Download FR data for all 108 8h coins from Binance data archive.
Period: 2022-01 to 2026-04
"""
import os
import requests
import zipfile
import pandas as pd
from io import BytesIO
from datetime import datetime, timezone

# All 8h interval coins that have spot + futures (from Binance API check)
COINS_8H = [
    'BTCUSDT', 'ETHUSDT', 'BCHUSDT', 'XRPUSDT', 'LTCUSDT', 'TRXUSDT', 'ETCUSDT',
    'LINKUSDT', 'XLMUSDT', 'ADAUSDT', 'DASHUSDT', 'ZECUSDT', 'BNBUSDT', 'ATOMUSDT',
    'IOTAUSDT', 'BATUSDT', 'VETUSDT', 'NEOUSDT', 'QTUMUSDT', 'IOSTUSDT', 'THETAUSDT',
    'ALGOUSDT', 'KNCUSDT', 'COMPUSDT', 'DOGEUSDT', 'BANDUSDT', 'RLCUSDT', 'SNXUSDT',
    'DOTUSDT', 'YFIUSDT', 'CRVUSDT', 'RUNEUSDT', 'SUSHIUSDT', 'EGLDUSDT', 'SOLUSDT',
    'UNIUSDT', 'AVAXUSDT', 'KSMUSDT', 'NEARUSDT', 'AAVEUSDT', 'FILUSDT', 'RSRUSDT',
    'BELUSDT', 'ZENUSDT', 'GRTUSDT', '1INCHUSDT', 'CHZUSDT', 'SANDUSDT', 'SFPUSDT',
    'COTIUSDT', 'CHRUSDT', 'MANAUSDT', 'HBARUSDT', 'ONEUSDT', 'CELRUSDT', 'HOTUSDT',
    'MTLUSDT', 'GTCUSDT', 'IOTXUSDT', 'C98USDT', 'DYDXUSDT', 'GALAUSDT', 'CELOUSDT',
    'ARUSDT', 'ARPAUSDT', 'CTSIUSDT', 'ENSUSDT', 'PEOPLEUSDT', 'ROSEUSDT', 'APEUSDT',
    'WOOUSDT', 'JASMYUSDT', 'OPUSDT', 'INJUSDT', 'STGUSDT', 'SPELLUSDT', 'LDOUSDT',
    'ICPUSDT', 'APTUSDT', 'QNTUSDT', 'FETUSDT', 'HIGHUSDT', 'MINAUSDT', 'ASTRUSDT',
    'GMXUSDT', 'CFXUSDT', 'STXUSDT', 'ACHUSDT', 'SSVUSDT', 'CKBUSDT', 'LQTYUSDT',
    'USDCUSDT', 'IDUSDT', 'ARBUSDT', 'JOEUSDT', 'HFTUSDT', 'XVSUSDT', 'EDUUSDT',
    'SUIUSDT', 'MAVUSDT', 'XVGUSDT', 'WLDUSDT', 'PENDLEUSDT', 'ARKMUSDT', 'AGLDUSDT',
    'BNTUSDT', 'SEIUSDT', 'BICOUSDT'
]

BASE_URL = "https://data.binance.vision/data/futures/um/monthly/fundingRate/{symbol}/{symbol}-fundingRate-{year}-{month:02d}.zip"
OUT_DIR = "./funding_rate_data_8h_expanded"

TRAIN_START = int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
TRAIN_END = int(datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000)

def download_coin(symbol):
    """Download all available monthly data for a coin"""
    os.makedirs(OUT_DIR, exist_ok=True)
    all_data = []
    
    for year in range(2022, 2027):
        for month in range(1, 13):
            if year == 2026 and month > 4:
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
            except Exception as e:
                pass
    
    if all_data:
        merged = pd.concat(all_data, ignore_index=True)
        merged = merged.sort_values('calc_time').reset_index(drop=True)
        return merged
    return None

def analyze_data(df, symbol):
    """Analyze downloaded data: gaps, training period coverage"""
    if df is None or len(df) == 0:
        return None
    
    # Date range
    first_ts = df['calc_time'].iloc[0]
    last_ts = df['calc_time'].iloc[-1]
    first = datetime.fromtimestamp(first_ts/1000, tz=timezone.utc)
    last = datetime.fromtimestamp(last_ts/1000, tz=timezone.utc)
    
    # Detect gaps (time diff > 10 hours for 8h interval coin)
    gaps = 0
    for i in range(1, len(df)):
        diff_h = (df['calc_time'].iloc[i] - df['calc_time'].iloc[i-1]) / (1000 * 3600)
        if diff_h > 10:
            gaps += 1
    
    # Count months in training period
    train_df = df[(df['calc_time'] >= TRAIN_START) & (df['calc_time'] <= TRAIN_END)]
    if len(train_df) > 0:
        train_first = datetime.fromtimestamp(train_df['calc_time'].iloc[0]/1000, tz=timezone.utc)
        train_last = datetime.fromtimestamp(train_df['calc_time'].iloc[-1]/1000, tz=timezone.utc)
        train_months = (train_last.year - train_first.year) * 12 + (train_last.month - train_first.month) + 1
    else:
        train_months = 0
    
    return {
        'symbol': symbol,
        'rows': len(df),
        'first': first.strftime('%Y-%m-%d'),
        'last': last.strftime('%Y-%m-%d'),
        'gaps': gaps,
        'train_rows': len(train_df),
        'train_months': train_months,
        'eligible': train_months >= 12
    }

def main():
    print("=" * 70)
    print("DOWNLOADING 8H UNIVERSE (108 COINS)")
    print("Period: 2022-01 to 2026-04")
    print("=" * 70)
    
    results = []
    
    for i, coin in enumerate(COINS_8H):
        print(f"\n[{i+1}/{len(COINS_8H)}] {coin}:", end=" ")
        
        df = download_coin(coin)
        
        if df is None or len(df) == 0:
            print("NO DATA")
            continue
        
        stats = analyze_data(df, coin)
        if stats:
            results.append(stats)
            df.to_csv(f"{OUT_DIR}/{coin}-fundingRate.csv", index=False)
            eligible_mark = "✅" if stats['eligible'] else "⚠️"
            print(f"{stats['rows']} rows, {stats['train_months']}mo train {eligible_mark}")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    eligible = [r for r in results if r['eligible']]
    not_eligible = [r for r in results if not r['eligible']]
    
    print(f"\nTotal downloaded: {len(results)} coins")
    print(f"Eligible (>= 12mo training): {len(eligible)} coins")
    print(f"Not eligible: {len(not_eligible)} coins")
    
    if not_eligible:
        print("\nNot eligible coins:")
        for r in not_eligible:
            print(f"  {r['symbol']}: {r['train_months']} months in training set")
    
    # Save summary
    summary_df = pd.DataFrame(results)
    summary_df.to_csv(f"{OUT_DIR}/_summary.csv", index=False)
    print(f"\nSummary saved to {OUT_DIR}/_summary.csv")

if __name__ == "__main__":
    main()
