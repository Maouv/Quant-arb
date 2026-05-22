#!/usr/bin/env python3
import os
import requests
import zipfile
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO

COINS = ['ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT', 'SUIUSDT', 'ADAUSDT', 
         'LINKUSDT', 'UNIUSDT', 'ZECUSDT', 'INJUSDT', 'NEARUSDT', 'AAVEUSDT', 
         'ONDOUSDT', 'TAOUSDT']

BASE_URL = "https://data.binance.vision/data/futures/um/monthly/fundingRate/{symbol}/{symbol}-fundingRate-{year}-{month:02d}.zip"
OUT_DIR = "./funding_rate_data"

def download_coin(symbol):
    os.makedirs(OUT_DIR, exist_ok=True)
    all_data = []
    
    for year in range(2022, 2026):
        for month in range(1, 13):
            if year == 2025 and month > 5:  # Skip future months
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
                    print(f"  Not found: {year}-{month:02d}")
            except Exception as e:
                print(f"  Error {year}-{month:02d}: {e}")
    
    if all_data:
        merged = pd.concat(all_data, ignore_index=True)
        merged.to_csv(f"{OUT_DIR}/{symbol}-fundingRate.csv", index=False)
        return merged
    return None

def analyze(symbol, df):
    rates = df['last_funding_rate'].dropna()
    total = len(rates)
    
    return {
        'Symbol': symbol,
        'Mean': rates.mean() * 100,
        'Median': rates.median() * 100,
        'Std': rates.std() * 100,
        'Min': rates.min() * 100,
        'Max': rates.max() * 100,
        '>0.01%': (np.abs(rates) > 0.0001).sum() / total * 100,
        '>0.05%': (np.abs(rates) > 0.0005).sum() / total * 100,
        '>0.10%': (np.abs(rates) > 0.001).sum() / total * 100,
        'Count': total
    }

def main():
    results = []
    all_rates = {}
    
    for coin in COINS:
        print(f"\nDownloading {coin}...")
        df = download_coin(coin)
        if df is not None:
            stats = analyze(coin, df)
            results.append(stats)
            all_rates[coin] = df['last_funding_rate'].dropna() * 100
            print(f"  Done: {stats['Count']} records")
    
    # Summary table
    df_results = pd.DataFrame(results)
    print("\n" + "="*100)
    print("FUNDING RATE SUMMARY (%)")
    print("="*100)
    print(df_results.to_string(index=False, float_format='%.4f'))
    
    # Plot
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    
    # Histogram
    ax1 = axes[0]
    for coin, rates in all_rates.items():
        ax1.hist(rates, bins=100, alpha=0.5, label=coin, density=True)
    ax1.set_xlabel('Funding Rate (%)')
    ax1.set_ylabel('Density')
    ax1.set_title('Funding Rate Distribution by Coin')
    ax1.legend(loc='upper right', fontsize=8, ncol=2)
    ax1.set_xlim(-0.5, 0.5)
    
    # Box plot
    ax2 = axes[1]
    ax2.boxplot([all_rates[c] for c in all_rates.keys()], labels=all_rates.keys())
    ax2.set_ylabel('Funding Rate (%)')
    ax2.set_title('Funding Rate Distribution Box Plot')
    ax2.tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    plt.savefig('funding_rate_distribution.png', dpi=150)
    print("\nPlot saved to funding_rate_distribution.png")

if __name__ == "__main__":
    main()
