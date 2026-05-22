#!/usr/bin/env python3
"""Phase 1b: Threshold Filter Analysis
Filter trades by entry threshold to see viability of selective entry.
Exit rule: FR flip sign (fixed, non-tunable).
Training set only: 2022-01-01 to 2024-12-31
"""
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# Universe (excluding NEAR)
UNIVERSE = ['ETHUSDT', 'XRPUSDT', 'DOGEUSDT', 'SUIUSDT', 'ADAUSDT',
            'LINKUSDT', 'UNIUSDT', 'ZECUSDT', 'INJUSDT', 'AAVEUSDT']

COST_BASELINE = {
    'ETHUSDT': 0.0814, 'XRPUSDT': 0.1018, 'DOGEUSDT': 0.1088,
    'SUIUSDT': 0.1119, 'ADAUSDT': 0.2002, 'LINKUSDT': 0.1113,
    'UNIUSDT': 0.1773, 'ZECUSDT': 0.0882, 'INJUSDT': 0.1562,
    'AAVEUSDT': 0.1275,
}

DATA_DIR = "./funding_rate_data"
TRAIN_START = int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
TRAIN_END = int(datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000)

# Entry thresholds to scan (not tune)
ENTRY_THRESHOLDS = [0.03, 0.05, 0.08, 0.10, 0.15]  # %


def load_training_data(symbol):
    df = pd.read_csv(f"{DATA_DIR}/{symbol}-fundingRate.csv")
    df = df[(df['calc_time'] >= TRAIN_START) & (df['calc_time'] <= TRAIN_END)]
    df = df.sort_values('calc_time').reset_index(drop=True)
    return df


def simulate_with_threshold(df, entry_threshold_pct, cost_rt):
    """
    Simulate trades with entry threshold filter.
    Entry: |FR| >= entry_threshold
    Exit: FR flip sign
    Returns list of trades with yield and duration.
    """
    fr = df['last_funding_rate'].values * 100  # Convert to %
    if len(fr) == 0:
        return []
    
    trades = []
    i = 0
    
    while i < len(fr):
        # Check for entry signal
        if abs(fr[i]) >= entry_threshold_pct:
            # Entry at this settlement
            entry_sign = 1 if fr[i] >= 0 else -1
            entry_idx = i
            
            # Hold until flip or end of data
            gross_yield = abs(fr[i])  # First settlement
            duration = 1
            i += 1
            
            while i < len(fr):
                current_sign = 1 if fr[i] >= 0 else -1
                
                # Exit condition: sign flip
                if current_sign != entry_sign:
                    break
                
                # Still same sign, collect yield
                gross_yield += abs(fr[i])
                duration += 1
                i += 1
            
            # Record trade
            net_yield = gross_yield - cost_rt
            trades.append({
                'entry_idx': entry_idx,
                'duration': duration,
                'gross_yield': gross_yield,
                'net_yield': net_yield,
                'entry_fr': abs(fr[entry_idx])
            })
        else:
            i += 1
    
    return trades


def analyze_threshold(symbol, df):
    """Analyze all entry thresholds for a coin"""
    cost = COST_BASELINE.get(symbol, 0.10)
    results = {}
    
    for thresh in ENTRY_THRESHOLDS:
        trades = simulate_with_threshold(df, thresh, cost)
        
        if not trades:
            results[thresh] = None
            continue
        
        df_trades = pd.DataFrame(trades)
        
        results[thresh] = {
            'num_trades': len(trades),
            'total_gross': df_trades['gross_yield'].sum(),
            'total_net': df_trades['net_yield'].sum(),
            'avg_net_per_trade': df_trades['net_yield'].mean(),
            'pct_positive': (df_trades['net_yield'] > 0).sum() / len(trades) * 100,
            'avg_duration': df_trades['duration'].mean(),
            'median_duration': df_trades['duration'].median(),
            'avg_entry_fr': df_trades['entry_fr'].mean(),
            'trades_per_year': len(trades) / 3,  # Rough annualization
            'annualized_yield': df_trades['net_yield'].sum() / 3,  # Rough annualization
        }
    
    return results


def main():
    print("=" * 80)
    print("PHASE 1b: THRESHOLD FILTER ANALYSIS")
    print("Entry thresholds: 0.03%, 0.05%, 0.08%, 0.10%, 0.15%")
    print("Exit rule: FR flip sign")
    print("=" * 80)
    
    all_results = {}
    
    for symbol in UNIVERSE:
        print(f"\n{'='*60}")
        print(f"ANALYZING: {symbol}")
        print(f"{'='*60}")
        
        df = load_training_data(symbol)
        print(f"Settlements in training set: {len(df)}")
        
        results = analyze_threshold(symbol, df)
        all_results[symbol] = results
        
        print(f"\n{'Thresh%':>8} | {'Trades':>6} | {'NetYield%':>10} | {'AvgNet%':>8} | {'%Pos':>6} | {'AvgDur':>6}")
        print("-" * 60)
        
        for thresh in ENTRY_THRESHOLDS:
            r = results[thresh]
            if r is None:
                print(f"{thresh:>8.2f} | {'NO TRADES':>48}")
            else:
                print(f"{thresh:>8.2f} | {r['num_trades']:>6} | {r['total_net']:>10.2f} | {r['avg_net_per_trade']:>8.4f} | {r['pct_positive']:>6.1f}% | {r['avg_duration']:>6.1f}")
    
    # Summary by threshold
    print("\n" + "=" * 80)
    print("SUMMARY: ANNUALIZED YIELD BY ENTRY THRESHOLD (Baseline Cost)")
    print("=" * 80)
    
    header = "Coin        " + " | ".join([f">{t:.2f}%" for t in ENTRY_THRESHOLDS])
    print(header)
    print("-" * len(header))
    
    for symbol in UNIVERSE:
        row = f"{symbol:11s}"
        for thresh in ENTRY_THRESHOLDS:
            r = all_results[symbol][thresh]
            if r is None:
                row += " |    N/A "
            else:
                row += f" | {r['annualized_yield']:>7.2f}%"
        print(row)
    
    # Summary: trades per year
    print("\n" + "=" * 80)
    print("SUMMARY: TRADES PER YEAR BY ENTRY THRESHOLD")
    print("=" * 80)
    
    print(header)
    print("-" * len(header))
    
    for symbol in UNIVERSE:
        row = f"{symbol:11s}"
        for thresh in ENTRY_THRESHOLDS:
            r = all_results[symbol][thresh]
            if r is None:
                row += " |    N/A "
            else:
                row += f" | {r['trades_per_year']:>7.1f} "
        print(row)


if __name__ == "__main__":
    main()
