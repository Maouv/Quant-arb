#!/usr/bin/env python3
"""Phase 1: Expanded Universe Analysis
Run threshold filter analysis for all 108 8h coins.
Training set: 2022-01-01 to 2024-12-31
"""
import os
import pandas as pd
import numpy as np
from datetime import datetime, timezone

DATA_DIR = "./funding_rate_data_8h_expanded"
TRAIN_START = int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
TRAIN_END = int(datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000)

# Flat cost tiers (we don't have per-coin data for 108 coins)
COST_LOW = 0.08   # Fee only
COST_MID = 0.12   # Average
COST_HIGH = 0.20  # Conservative for smaller coins

ENTRY_THRESHOLDS = [0.03, 0.05, 0.08, 0.10]


def load_training_data(filepath):
    """Load CSV and filter to training set"""
    df = pd.read_csv(filepath)
    df = df[(df['calc_time'] >= TRAIN_START) & (df['calc_time'] <= TRAIN_END)]
    df = df.sort_values('calc_time').reset_index(drop=True)
    return df


def calculate_train_months(df):
    """Calculate actual months in training set"""
    if len(df) == 0:
        return 0
    first = datetime.fromtimestamp(df['calc_time'].iloc[0]/1000, tz=timezone.utc)
    last = datetime.fromtimestamp(df['calc_time'].iloc[-1]/1000, tz=timezone.utc)
    months = (last.year - first.year) * 12 + (last.month - first.month) + 1
    return months


def simulate_trades(df, entry_threshold_pct, cost_rt):
    """
    Simulate trades with entry threshold filter.
    Entry: |FR| >= entry_threshold
    Exit: FR flip sign
    """
    fr = df['last_funding_rate'].values * 100  # Convert to %
    if len(fr) == 0:
        return []
    
    trades = []
    i = 0
    
    while i < len(fr):
        if abs(fr[i]) >= entry_threshold_pct:
            entry_sign = 1 if fr[i] >= 0 else -1
            entry_idx = i
            
            gross_yield = abs(fr[i])
            duration = 1
            i += 1
            
            while i < len(fr):
                current_sign = 1 if fr[i] >= 0 else -1
                if current_sign != entry_sign:
                    break
                gross_yield += abs(fr[i])
                duration += 1
                i += 1
            
            net_yield = gross_yield - cost_rt
            trades.append({
                'duration': duration,
                'gross_yield': gross_yield,
                'net_yield': net_yield,
                'entry_fr': abs(fr[entry_idx])
            })
        else:
            i += 1
    
    return trades


def analyze_coin(filepath, symbol):
    """Analyze a single coin across all thresholds and cost tiers"""
    df = load_training_data(filepath)
    
    if len(df) == 0:
        return None
    
    train_months = calculate_train_months(df)
    years = train_months / 12
    
    results = {'symbol': symbol, 'train_months': train_months, 'settlements': len(df)}
    
    for thresh in ENTRY_THRESHOLDS:
        for cost_name, cost in [('low', COST_LOW), ('mid', COST_MID), ('high', COST_HIGH)]:
            trades = simulate_trades(df, thresh, cost)
            
            if not trades:
                results[f'{thresh}_{cost_name}_trades'] = 0
                results[f'{thresh}_{cost_name}_ann_yield'] = 0
                results[f'{thresh}_{cost_name}_avg_net'] = 0
                results[f'{thresh}_{cost_name}_pct_pos'] = 0
                results[f'{thresh}_{cost_name}_trades_yr'] = 0
                continue
            
            total_net = sum(t['net_yield'] for t in trades)
            avg_net = np.mean([t['net_yield'] for t in trades])
            pct_pos = sum(1 for t in trades if t['net_yield'] > 0) / len(trades) * 100
            avg_dur = np.mean([t['duration'] for t in trades])
            trades_yr = len(trades) / years if years > 0 else 0
            ann_yield = total_net / years if years > 0 else 0
            
            results[f'{thresh}_{cost_name}_trades'] = len(trades)
            results[f'{thresh}_{cost_name}_ann_yield'] = ann_yield
            results[f'{thresh}_{cost_name}_avg_net'] = avg_net
            results[f'{thresh}_{cost_name}_pct_pos'] = pct_pos
            results[f'{thresh}_{cost_name}_avg_dur'] = avg_dur
            results[f'{thresh}_{cost_name}_trades_yr'] = trades_yr
    
    return results


def main():
    print("=" * 80)
    print("PHASE 1: EXPANDED UNIVERSE ANALYSIS")
    print(f"Data dir: {DATA_DIR}")
    print("Training: 2022-01-01 to 2024-12-31")
    print("=" * 80)
    
    # Get all CSV files
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv') and not f.startswith('_')]
    print(f"\nFound {len(files)} coin files")
    
    all_results = []
    
    for i, filename in enumerate(files):
        symbol = filename.replace('-fundingRate.csv', '')
        filepath = os.path.join(DATA_DIR, filename)
        
        print(f"[{i+1}/{len(files)}] {symbol}...", end=" ")
        
        result = analyze_coin(filepath, symbol)
        if result:
            all_results.append(result)
            # Quick summary at threshold 0.05%, mid cost
            trades_yr = result.get('0.05_mid_trades_yr', 0)
            ann = result.get('0.05_mid_ann_yield', 0)
            print(f"{result['train_months']}mo, {trades_yr:.1f} trades/yr, {ann:.2f}% ann")
        else:
            print("NO DATA")
    
    # Convert to DataFrame
    df = pd.DataFrame(all_results)
    
    # Summary outputs
    print("\n" + "=" * 80)
    print("SUMMARY: TOP 20 COINS BY TRADES/YEAR (threshold 0.05%, mid cost)")
    print("=" * 80)
    
    top20 = df.nlargest(20, '0.05_mid_trades_yr')[['symbol', 'train_months', '0.05_mid_trades_yr', 
                                                    '0.05_mid_ann_yield', '0.05_mid_pct_pos', '0.05_mid_avg_dur']]
    print(top20.to_string(index=False, float_format='%.2f'))
    
    # Aggregate stats
    print("\n" + "=" * 80)
    print("AGGREGATE STATISTICS (threshold 0.05%, mid cost)")
    print("=" * 80)
    
    total_trades_yr = df['0.05_mid_trades_yr'].sum()
    avg_trades_yr = df['0.05_mid_trades_yr'].mean()
    avg_hold = df['0.05_mid_avg_dur'].mean() * 8 / 24  # Convert settlements to days
    
    print(f"Total coins analyzed: {len(df)}")
    print(f"Total trades/year (all coins): {total_trades_yr:.0f}")
    print(f"Avg trades/year per coin: {avg_trades_yr:.1f}")
    print(f"Avg hold duration: {avg_hold:.1f} days")
    
    # Capital utilization estimate (with 3 pair slots)
    max_pairs = 3
    utilization = (total_trades_yr * avg_hold) / (365 * max_pairs) * 100
    print(f"\nCapital utilization estimate (3 slots): {utilization:.1f}%")
    
    # Tier breakdown
    print("\n" + "=" * 80)
    print("OPPORTUNITY FREQUENCY TIERS (threshold 0.05%)")
    print("=" * 80)
    
    high_freq = df[df['0.05_mid_trades_yr'] >= 10]
    mid_freq = df[(df['0.05_mid_trades_yr'] >= 5) & (df['0.05_mid_trades_yr'] < 10)]
    low_freq = df[df['0.05_mid_trades_yr'] < 5]
    
    print(f"High frequency (>= 10 trades/yr): {len(high_freq)} coins")
    print(f"Mid frequency (5-10 trades/yr): {len(mid_freq)} coins")
    print(f"Low frequency (< 5 trades/yr): {len(low_freq)} coins")
    
    if len(high_freq) > 0:
        print(f"\nHigh frequency coins: {', '.join(high_freq['symbol'].tolist())}")
    
    # Save results
    df.to_csv(f"{DATA_DIR}/_phase1_results.csv", index=False)
    print(f"\nFull results saved to {DATA_DIR}/_phase1_results.csv")


if __name__ == "__main__":
    main()
