"""
Stress test analysis for crash windows.
"""
import pandas as pd
from typing import Optional
import sys
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent.parent))
from config import STRESS_WINDOWS, STRESS_MULTIPLIERS, RECOVERY_DAYS


def filterTradesInWindow(tradeLog: list[dict], 
                          windowStart: str, windowEnd: str) -> list[dict]:
    """
    Filter trades that overlap with a time window.
    
    Args:
        tradeLog: List of trade dicts
        windowStart: Window start date (YYYY-MM-DD)
        windowEnd: Window end date (YYYY-MM-DD)
    
    Returns:
        Filtered list of trades
    """
    start = pd.Timestamp(windowStart, tz="UTC")
    end = pd.Timestamp(windowEnd, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    
    trades = []
    for trade in tradeLog:
        entry = pd.Timestamp(trade["entry_time"])
        exitTime = pd.Timestamp(trade["exit_time"])
        
        # Trade overlaps if any part is in window
        if entry <= end and exitTime >= start:
            trades.append(trade)
    
    return trades


def applyCostMultiplier(trade: dict, multiplier: float,
                         windowStart: pd.Timestamp, windowEnd: pd.Timestamp) -> dict:
    """
    Apply cost multiplier to settlements within window.
    
    Args:
        trade: Trade dict
        multiplier: Cost multiplier (e.g., 3.0)
        windowStart: Window start timestamp
        windowEnd: Window end timestamp
    
    Returns:
        Trade dict with adjusted net
    """
    entry = pd.Timestamp(trade["entry_time"])
    exitTime = pd.Timestamp(trade["exit_time"])
    
    holdSettlements = trade["hold_settlements"]
    if holdSettlements == 0:
        holdSettlements = 1
    
    costPerSettlement = trade["cost_rt_pct"] / holdSettlements
    
    # Count settlements in window
    adjustedCost = 0.0
    current = entry
    
    for i in range(holdSettlements):
        settlementTime = entry + pd.Timedelta(hours=8*i)
        
        if windowStart <= settlementTime <= windowEnd:
            adjustedCost += costPerSettlement * multiplier
        else:
            adjustedCost += costPerSettlement
    
    adjustedNet = trade["gross_pct"] - adjustedCost
    adjustedNetDollar = adjustedNet / 100 * 300.0  # SIZE_PER_PAIR
    
    adjustedTrade = trade.copy()
    adjustedTrade["cost_rt_pct"] = adjustedCost
    adjustedTrade["net_pct"] = adjustedNet
    adjustedTrade["net_dollar"] = adjustedNetDollar
    
    return adjustedTrade


def runStressTest(tradeLog: list[dict], windowName: str,
                   windowStart: str, windowEnd: str,
                   multipliers: list[int] = None) -> dict:
    """
    Run stress test for a crash window.
    
    Args:
        tradeLog: List of trade dicts
        windowName: Name of crash window
        windowStart: Window start date
        windowEnd: Window end date
        multipliers: List of cost multipliers
    
    Returns:
        Dict with stress test results
    """
    if multipliers is None:
        multipliers = STRESS_MULTIPLIERS
    
    start = pd.Timestamp(windowStart, tz="UTC")
    end = pd.Timestamp(windowEnd, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    
    # Filter trades in window
    windowTrades = filterTradesInWindow(tradeLog, windowStart, windowEnd)
    
    results = {
        "window_name": windowName,
        "window_start": windowStart,
        "window_end": windowEnd,
        "trades_in_window": len(windowTrades),
        "base_net_dollar": sum(t["net_dollar"] for t in windowTrades),
    }
    
    # Apply multipliers
    for mult in multipliers:
        adjustedTrades = [
            applyCostMultiplier(t, float(mult), start, end)
            for t in windowTrades
        ]
        netDollar = sum(t["net_dollar"] for t in adjustedTrades)
        results[f"net_{mult}x"] = netDollar
    
    # Calculate break-even multiplier
    baseNet = results["base_net_dollar"]
    if baseNet > 0:
        # Find where net turns negative
        for mult in multipliers:
            if results[f"net_{mult}x"] < 0:
                results["break_even_multiplier"] = mult - 1
                break
        else:
            results["break_even_multiplier"] = multipliers[-1]
    else:
        results["break_even_multiplier"] = 1
    
    return results


def analyzeRecovery(tradeLog: list[dict], windowEnd: str,
                     recoveryDays: int = RECOVERY_DAYS) -> dict:
    """
    Analyze recovery after crash window.
    
    Args:
        tradeLog: List of trade dicts
        windowEnd: Window end date
        recoveryDays: Number of days to analyze
    
    Returns:
        Dict with recovery metrics
    """
    windowEndTs = pd.Timestamp(windowEnd, tz="UTC")
    recoveryEnd = windowEndTs + pd.Timedelta(days=recoveryDays)
    
    # Filter trades in recovery period
    recoveryTrades = []
    for trade in tradeLog:
        entry = pd.Timestamp(trade["entry_time"])
        if windowEndTs < entry <= recoveryEnd:
            recoveryTrades.append(trade)
    
    if not recoveryTrades:
        return {"recovery": "no_trades"}
    
    df = pd.DataFrame(recoveryTrades)
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df["days_after"] = (df["entry_time"] - windowEndTs).dt.days
    
    # Calculate cumulative P&L
    df = df.sort_values("entry_time")
    df["cumulative_pnl"] = df["net_dollar"].cumsum()
    
    # Find max drawdown
    peak = 0.0
    maxDrawdown = 0.0
    maxDrawdownDuration = 0
    drawdownStart = None
    
    for _, row in df.iterrows():
        if row["cumulative_pnl"] > peak:
            peak = row["cumulative_pnl"]
            if drawdownStart is not None:
                duration = (row["entry_time"] - drawdownStart).days
                maxDrawdownDuration = max(maxDrawdownDuration, duration)
                drawdownStart = None
        else:
            dd = row["cumulative_pnl"] - peak
            maxDrawdown = min(maxDrawdown, dd)
            if drawdownStart is None:
                drawdownStart = row["entry_time"]
    
    # Recovery time
    finalPnl = df["cumulative_pnl"].iloc[-1] if len(df) > 0 else 0
    if finalPnl >= 0:
        # Find when cumulative turned positive
        recoveryPoint = df[df["cumulative_pnl"] >= 0]
        if not recoveryPoint.empty:
            recoveryTime = (recoveryPoint.iloc[0]["entry_time"] - windowEndTs).days
        else:
            recoveryTime = recoveryDays
    else:
        recoveryTime = recoveryDays  # Unrecovered
    
    # Period analysis
    period1 = df[df["days_after"] <= 30]
    period2 = df[(df["days_after"] > 30) & (df["days_after"] <= 60)]
    period3 = df[(df["days_after"] > 60) & (df["days_after"] <= 90)]
    
    return {
        "recovery_trades": len(recoveryTrades),
        "total_pnl": df["net_dollar"].sum(),
        "max_drawdown": maxDrawdown,
        "max_drawdown_duration": maxDrawdownDuration,
        "recovery_time_days": recoveryTime,
        "avg_pnl_day_1_30": period1["net_dollar"].mean() if len(period1) > 0 else 0,
        "avg_pnl_day_31_60": period2["net_dollar"].mean() if len(period2) > 0 else 0,
        "avg_pnl_day_61_90": period3["net_dollar"].mean() if len(period3) > 0 else 0,
    }


def formatStressReport(results: dict, recovery: dict) -> str:
    """
    Format stress test results as text report.
    
    Args:
        results: Stress test results dict
        recovery: Recovery analysis dict
    
    Returns:
        Formatted text report
    """
    lines = [f"\n=== {results['window_name']} STRESS TEST ==="]
    lines.append(f"Period: {results['window_start']} to {results['window_end']}")
    lines.append("\n--- SURVIVAL ---")
    lines.append(f"Trades in window: {results['trades_in_window']}")
    lines.append(f"Net yield (1x cost): ${results['base_net_dollar']:.2f}")
    
    for mult in STRESS_MULTIPLIERS:
        key = f"net_{mult}x"
        if key in results:
            lines.append(f"Net yield ({mult}x cost): ${results[key]:.2f}")
    
    lines.append(f"Break-even multiplier: {results.get('break_even_multiplier', 'N/A')}x")
    
    if recovery and "recovery" not in recovery:
        lines.append("\n--- RECOVERY (90 days) ---")
        lines.append(f"Recovery trades: {recovery.get('recovery_trades', 0)}")
        lines.append(f"Max drawdown: ${recovery.get('max_drawdown', 0):.2f}")
        lines.append(f"Recovery time: {recovery.get('recovery_time_days', 90)} days")
    
    return "\n".join(lines)
