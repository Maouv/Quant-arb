"""
Rolling monthly statistics analysis.
"""
import pandas as pd
from typing import Optional
import sys
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent.parent))


def calculateMonthlyStats(tradeLog: list[dict]) -> pd.DataFrame:
    """
    Calculate rolling monthly statistics.
    
    Args:
        tradeLog: List of trade dicts
    
    Returns:
        DataFrame with monthly stats
    """
    if not tradeLog:
        return pd.DataFrame()
    
    df = pd.DataFrame(tradeLog)
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df["month"] = df["entry_time"].dt.to_period("M")
    
    monthly = df.groupby("month").agg(
        trades=("symbol", "count"),
        win_rate=("net_pct", lambda x: (x > 0).sum() / len(x) * 100),
        avg_net_pct=("net_pct", "mean"),
        total_net_dollar=("net_dollar", "sum"),
        avg_hold=("hold_settlements", "mean"),
    ).reset_index()
    
    return monthly


def flagAnomalousMonths(monthlyDf: pd.DataFrame) -> pd.DataFrame:
    """
    Flag months with anomalous metrics.
    
    Flags:
    - T drop > 30% from median
    - Win rate < 40%
    
    Args:
        monthlyDf: DataFrame from calculateMonthlyStats
    
    Returns:
        DataFrame with flags
    """
    if monthlyDf.empty:
        return monthlyDf
    
    medianTrades = monthlyDf["trades"].median()
    
    monthlyDf["flag_low_trades"] = monthlyDf["trades"] < medianTrades * 0.7
    monthlyDf["flag_low_winrate"] = monthlyDf["win_rate"] < 40
    
    return monthlyDf


def formatMonthlyReport(monthlyDf: pd.DataFrame) -> str:
    """
    Format monthly stats as text report.
    
    Args:
        monthlyDf: DataFrame with monthly stats
    
    Returns:
        Formatted text report
    """
    if monthlyDf.empty:
        return "No trades to analyze."
    
    lines = ["=== MONTHLY STATISTICS ===\n"]
    lines.append(f"{'Month':<10} {'Trades':>8} {'WinRate':>10} {'AvgNet%':>10} {'Total$':>10} Flags")
    lines.append("-" * 60)
    
    for _, row in monthlyDf.iterrows():
        flags = []
        if row.get("flag_low_trades", False):
            flags.append("LOW_T")
        if row.get("flag_low_winrate", False):
            flags.append("LOW_WR")
        
        flagStr = ",".join(flags) if flags else ""
        monthStr = str(row["month"])
        
        lines.append(
            f"{monthStr:<10} {row['trades']:>8} {row['win_rate']:>9.1f}% "
            f"{row['avg_net_pct']:>9.4f}% {row['total_net_dollar']:>9.2f}$ {flagStr}"
        )
    
    return "\n".join(lines)
