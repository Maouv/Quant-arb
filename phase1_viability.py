#!/usr/bin/env python3
"""Phase 1: Viability Analysis
Training set only: 2022-01-01 to 2024-12-31
"""
import os
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# Universe (excluding NEAR from backtest per Phase 0 decision)
UNIVERSE = ['ETHUSDT', 'XRPUSDT', 'DOGEUSDT', 'SUIUSDT', 'ADAUSDT',
            'LINKUSDT', 'UNIUSDT', 'ZECUSDT', 'INJUSDT', 'AAVEUSDT']
# NEAR excluded from backtest - cost structurally higher than historical yield

# Cost per coin (from Phase 0, sampled 19 May 2026)
# Total RT% = fee(0.08%) + Spread RT% + Slippage RT%
COST_BASELINE = {
    'ETHUSDT': 0.0814,
    'XRPUSDT': 0.1018,
    'DOGEUSDT': 0.1088,
    'SUIUSDT': 0.1119,
    'ADAUSDT': 0.2002,
    'LINKUSDT': 0.1113,
    'UNIUSDT': 0.1773,
    'ZECUSDT': 0.0882,
    'INJUSDT': 0.1562,
    'AAVEUSDT': 0.1275,
    'NEARUSDT': 0.2655,  # Included for reference but excluded from analysis
}

FEE_ONLY = 0.08  # Lower bound
DATA_DIR = "./funding_rate_data"
TRAIN_START = int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
TRAIN_END = int(datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000)

THRESHOLDS = [0.01, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20]  # %


def load_training_data(symbol):
    """Load and filter to training set only"""
    df = pd.read_csv(f"{DATA_DIR}/{symbol}-fundingRate.csv")
    df = df[(df['calc_time'] >= TRAIN_START) & (df['calc_time'] <= TRAIN_END)]
    df = df.sort_values('calc_time').reset_index(drop=True)
    return df


def identify_runs(df):
    """
    Identify consecutive runs where FR maintains same sign.
    A run starts when FR crosses zero (changes sign) or at start of data.
    Returns list of runs with: start_idx, end_idx, length, sum_fr, sign
    """
    runs = []
    fr = df['last_funding_rate'].values
    
    if len(fr) == 0:
        return runs
    
    # Determine sign (0 is positive for simplicity)
    signs = np.where(fr >= 0, 1, -1)
    
    current_sign = signs[0]
    start_idx = 0
    sum_fr = 0
    
    for i in range(len(fr)):
        if signs[i] != current_sign:
            # Run ended
            runs.append({
                'start_idx': start_idx,
                'end_idx': i - 1,
                'length': i - start_idx,
                'sum_fr': sum_fr,
                'sign': current_sign
            })
            # New run starts
            start_idx = i
            current_sign = signs[i]
            sum_fr = fr[i]
        else:
            sum_fr += fr[i]
    
    # Last run
    runs.append({
        'start_idx': start_idx,
        'end_idx': len(fr) - 1,
        'length': len(fr) - start_idx,
        'sum_fr': sum_fr,
        'sign': current_sign
    })
    
    return runs


def calculate_yield_per_trade(runs, cost_rt):
    """
    For each run (trade), calculate net yield.
    Net = |sum_fr| - cost_rt
    """
    results = []
    for run in runs:
        gross = abs(run['sum_fr']) * 100  # Convert to %
        net = gross - cost_rt
        results.append({
            'length': run['length'],
            'gross_yield': gross,
            'net_yield': net,
            'sign': run['sign']
        })
    return results


def deliverable_1_yield_per_coin(symbol, df):
    """Historical yield per coin after cost"""
    runs = identify_runs(df)
    
    if not runs:
        return None
    
    baseline = COST_BASELINE.get(symbol, 0.10)
    
    # Three cost scenarios
    results = {}
    for scenario, cost in [('fee_only', FEE_ONLY), ('baseline', baseline), ('2x_baseline', baseline * 2)]:
        trades = calculate_yield_per_trade(runs, cost)
        df_trades = pd.DataFrame(trades)
        
        # Breakdown by run length
        breakdown = {
            '1-2': df_trades[df_trades['length'] <= 2],
            '3-5': df_trades[(df_trades['length'] >= 3) & (df_trades['length'] <= 5)],
            '5+': df_trades[df_trades['length'] > 5]
        }
        
        results[scenario] = {
            'total_trades': len(trades),
            'total_gross': df_trades['gross_yield'].sum(),
            'total_net': df_trades['net_yield'].sum(),
            'avg_net_per_trade': df_trades['net_yield'].mean(),
            'pct_positive': (df_trades['net_yield'] > 0).sum() / len(trades) * 100,
            'breakdown': {
                k: {
                    'count': len(v),
                    'avg_net': v['net_yield'].mean() if len(v) > 0 else 0,
                    'pct_positive': (v['net_yield'] > 0).sum() / len(v) * 100 if len(v) > 0 else 0
                } for k, v in breakdown.items()
            }
        }
    
    return results


def deliverable_2_frequency(df):
    """Frequency of opportunity per threshold"""
    fr_abs = np.abs(df['last_funding_rate'].values) * 100  # Convert to %
    total = len(fr_abs)
    
    results = {}
    for thresh in THRESHOLDS:
        count = (fr_abs >= thresh).sum()
        results[f'>{thresh}%'] = {
            'count': int(count),
            'pct': count / total * 100
        }
    
    return results


def deliverable_3_flip_frequency(df, runs):
    """Funding flip frequency analysis"""
    if not runs:
        return None
    
    lengths = [r['length'] for r in runs]
    
    return {
        'total_flips': len(runs) - 1,  # First run is not a flip
        'total_settlements': len(df),
        'avg_run_length': np.mean(lengths),
        'median_run_length': np.median(lengths),
        'p25': np.percentile(lengths, 25),
        'p75': np.percentile(lengths, 75),
        'p90': np.percentile(lengths, 90),
        'min_run': min(lengths),
        'max_run': max(lengths)
    }


def deliverable_4_worst_drawdown(runs, cost_rt):
    """Worst case drawdown - consecutive losing trades"""
    trades = calculate_yield_per_trade(runs, cost_rt)
    
    # Find worst streak of negative net yields
    max_drawdown = 0
    current_drawdown = 0
    worst_streak = 0
    current_streak = 0
    
    for trade in trades:
        if trade['net_yield'] < 0:
            current_drawdown += abs(trade['net_yield'])
            current_streak += 1
        else:
            if current_drawdown > max_drawdown:
                max_drawdown = current_drawdown
                worst_streak = current_streak
            current_drawdown = 0
            current_streak = 0
    
    # Check final streak
    if current_drawdown > max_drawdown:
        max_drawdown = current_drawdown
        worst_streak = current_streak
    
    return {
        'max_drawdown': max_drawdown,
        'worst_streak_length': worst_streak
    }


def main():
    print("=" * 80)
    print("PHASE 1: VIABILITY ANALYSIS")
    print("Training Set: 2022-01-01 to 2024-12-31")
    print("=" * 80)
    
    all_results = {}
    
    for symbol in UNIVERSE:
        print(f"\n{'='*40}")
        print(f"ANALYZING: {symbol}")
        print(f"{'='*40}")
        
        df = load_training_data(symbol)
        print(f"Settlements in training set: {len(df)}")
        
        runs = identify_runs(df)
        print(f"Total runs (trades): {len(runs)}")
        
        if len(runs) == 0:
            print("  No data, skipping...")
            continue
        
        # Deliverable 1: Yield per coin
        print("\n--- DELIVERABLE 1: YIELD PER COIN ---")
        yield_results = deliverable_1_yield_per_coin(symbol, df)
        
        for scenario, data in yield_results.items():
            print(f"\n  [{scenario}] Cost: {FEE_ONLY if scenario=='fee_only' else COST_BASELINE.get(symbol, 0.10) * (2 if scenario=='2x_baseline' else 1):.4f}%")
            print(f"    Total trades: {data['total_trades']}")
            print(f"    Total net yield: {data['total_net']:.4f}%")
            print(f"    Avg net/trade: {data['avg_net_per_trade']:.4f}%")
            print(f"    % positive: {data['pct_positive']:.1f}%")
            print(f"    Breakdown by run length:")
            for bucket, stats in data['breakdown'].items():
                print(f"      {bucket} settlements: {stats['count']} trades, avg net {stats['avg_net']:.4f}%, {stats['pct_positive']:.1f}% positive")
        
        # Deliverable 2: Frequency per threshold
        print("\n--- DELIVERABLE 2: FREQUENCY PER THRESHOLD ---")
        freq = deliverable_2_frequency(df)
        for thresh, stats in freq.items():
            print(f"  {thresh}: {stats['count']} settlements ({stats['pct']:.2f}%)")
        
        # Deliverable 3: Flip frequency
        print("\n--- DELIVERABLE 3: FLIP FREQUENCY ---")
        flip = deliverable_3_flip_frequency(df, runs)
        print(f"  Total flips: {flip['total_flips']}")
        print(f"  Avg run length: {flip['avg_run_length']:.1f} settlements")
        print(f"  Run length dist: p25={flip['p25']:.0f}, median={flip['median_run_length']:.0f}, p75={flip['p75']:.0f}, p90={flip['p90']:.0f}")
        print(f"  Range: {flip['min_run']} - {flip['max_run']} settlements")
        
        # Deliverable 4: Worst drawdown (baseline cost only)
        print("\n--- DELIVERABLE 4: WORST CASE DRAWDOWN ---")
        baseline = COST_BASELINE.get(symbol, 0.10)
        for cost_name, cost in [('fee_only', FEE_ONLY), ('baseline', baseline), ('2x_baseline', baseline * 2)]:
            dd = deliverable_4_worst_drawdown(runs, cost)
            print(f"  [{cost_name}] Max drawdown: {dd['max_drawdown']:.4f}% over {dd['worst_streak_length']} consecutive losing trades")
        
        all_results[symbol] = {
            'yield': yield_results,
            'frequency': freq,
            'flip': flip
        }
    
    # Summary table
    print("\n" + "=" * 80)
    print("SUMMARY TABLE")
    print("=" * 80)
    print("\n{:12s} | {:>10s} | {:>10s} | {:>10s} | {:>8s}".format(
        "Symbol", "Net Yield%", "Avg/Trade%", "% Positive", "Avg Run"
    ))
    print("-" * 65)
    for symbol in UNIVERSE:
        if symbol in all_results:
            y = all_results[symbol]['yield']['baseline']
            f = all_results[symbol]['flip']
            print("{:12s} | {:>10.4f} | {:>10.4f} | {:>8.1f}% | {:>8.1f}".format(
                symbol, y['total_net'], y['avg_net_per_trade'], y['pct_positive'], f['avg_run_length']
            ))


if __name__ == "__main__":
    main()
