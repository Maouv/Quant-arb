"""
Drawdown analysis: max DD, consecutive losses, recovery.
"""
import pandas as pd
import sys
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent.parent))


def calculateDrawdownMetrics(equityCurve: pd.DataFrame) -> dict:
    """
    Calculate drawdown metrics from equity curve.
    
    Args:
        equityCurve: DataFrame with ['timestamp', 'equity', 'drawdown_dollar', 'drawdown_pct']
    
    Returns:
        Dict with drawdown metrics
    """
    if equityCurve.empty:
        return {}
    
    df = equityCurve.copy()
    
    # Max drawdown
    maxDrawdownDollar = df["drawdown_dollar"].min()
    maxDrawdownPct = df["drawdown_pct"].min()
    
    # Max drawdown duration (in settlements)
    peakIdx = 0
    maxDuration = 0
    currentDuration = 0
    
    for i, row in df.iterrows():
        if row["drawdown_dollar"] >= 0:
            currentDuration = 0
            peakIdx = i
        else:
            currentDuration += 1
            maxDuration = max(maxDuration, currentDuration)
    
    # Convert to days (8h settlements)
    maxDurationDays = maxDuration * 8 / 24
    
    return {
        "max_drawdown_dollar": maxDrawdownDollar,
        "max_drawdown_pct": maxDrawdownPct,
        "max_drawdown_duration_days": maxDurationDays,
    }


def calculateConsecutiveLosses(tradeLog: list[dict]) -> dict:
    """
    Calculate max consecutive losing trades and negative days.
    
    Args:
        tradeLog: List of trade dicts
    
    Returns:
        Dict with consecutive loss metrics
    """
    if not tradeLog:
        return {"max_consecutive_losses": 0, "max_consecutive_neg_days": 0}
    
    df = pd.DataFrame(tradeLog)
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df = df.sort_values("entry_time")
    
    # Consecutive losses (trades)
    maxConsecLosses = 0
    currentConsec = 0
    
    for _, row in df.iterrows():
        if row["net_dollar"] < 0:
            currentConsec += 1
            maxConsecLosses = max(maxConsecLosses, currentConsec)
        else:
            currentConsec = 0
    
    # Consecutive negative days
    df["date"] = df["entry_time"].dt.date
    dailyPnl = df.groupby("date")["net_dollar"].sum()
    
    maxConsecNegDays = 0
    currentConsec = 0
    
    for pnl in dailyPnl:
        if pnl < 0:
            currentConsec += 1
            maxConsecNegDays = max(maxConsecNegDays, currentConsec)
        else:
            currentConsec = 0
    
    return {
        "max_consecutive_losses": maxConsecLosses,
        "max_consecutive_neg_days": maxConsecNegDays,
    }


def analyzeShortHoldFragility(tradeLog: list[dict], 
                                threshold: int = 3) -> dict:
    """
    Analyze trades with short hold (<= threshold settlements).
    
    Args:
        tradeLog: List of trade dicts
        threshold: Hold threshold (default 3)
    
    Returns:
        Dict with short hold analysis
    """
    shortTrades = [t for t in tradeLog if t["hold_settlements"] <= threshold]
    
    if not shortTrades:
        return {
            "short_hold_trades": 0,
            "short_hold_net_total": 0,
            "short_hold_win_rate": 0,
        }
    
    netTotal = sum(t["net_dollar"] for t in shortTrades)
    wins = sum(1 for t in shortTrades if t["net_pct"] > 0)
    winRate = wins / len(shortTrades) * 100
    
    return {
        "short_hold_trades": len(shortTrades),
        "short_hold_net_total": netTotal,
        "short_hold_win_rate": winRate,
        "short_hold_avg_net": netTotal / len(shortTrades),
    }


def calculatePhase1Reconciliation(tradeLog: list[dict],
                                   sizePerPair: float = 300.0) -> dict:
    """
    Calculate Phase 1 vs Phase 3 yield reconciliation.
    
    Phase 1 counts FR at signal (entry_fr, index t) as collected.
    Phase 3 only collects from t+1 onward (entry_collect_fr).
    
    Overstate per trade = (entry_fr - entry_collect_fr) / 100 * size_per_pair
    
    Args:
        tradeLog: List of trade dicts
        sizePerPair: Position size
    
    Returns:
        Dict with reconciliation metrics
    """
    if not tradeLog:
        return {"phase1_overstate_total": 0}
    
    overstateDollarList = []
    for t in tradeLog:
        entryFr = t.get("entry_fr", 0.0)
        entryCollectFr = t.get("entry_collect_fr", 0.0)
        overstatePct = entryFr - entryCollectFr  # already in %
        overstateDollar = overstatePct / 100 * sizePerPair
        overstateDollarList.append(overstateDollar)
    
    totalOverstate = sum(overstateDollarList)
    avgOverstate = totalOverstate / len(tradeLog)
    
    return {
        "phase1_overstate_dollar_total": totalOverstate,
        "avg_overstate_per_trade_dollar": avgOverstate,
    }


def formatDrawdownReport(ddMetrics: dict, consecMetrics: dict,
                           shortHold: dict, reconciliation: dict) -> str:
    """
    Format drawdown analysis as text report.
    
    Args:
        ddMetrics: Drawdown metrics
        consecMetrics: Consecutive loss metrics
        shortHold: Short hold fragility analysis
        reconciliation: Phase 1 reconciliation
    
    Returns:
        Formatted text report
    """
    lines = ["=== DRAWDOWN & RISK ANALYSIS ===\n"]
    
    lines.append("--- Drawdown ---")
    lines.append(f"Max drawdown: ${ddMetrics.get('max_drawdown_dollar', 0):.2f} "
                 f"({ddMetrics.get('max_drawdown_pct', 0):.2f}%)")
    lines.append(f"Max drawdown duration: {ddMetrics.get('max_drawdown_duration_days', 0):.1f} days")
    
    lines.append("\n--- Consecutive Losses ---")
    lines.append(f"Max consecutive losing trades: {consecMetrics.get('max_consecutive_losses', 0)}")
    lines.append(f"Max consecutive negative days: {consecMetrics.get('max_consecutive_neg_days', 0)}")
    
    lines.append("\n--- Short Hold Fragility (<=3 settlements) ---")
    lines.append(f"Short hold trades: {shortHold.get('short_hold_trades', 0)}")
    lines.append(f"Short hold net total: ${shortHold.get('short_hold_net_total', 0):.2f}")
    lines.append(f"Short hold win rate: {shortHold.get('short_hold_win_rate', 0):.1f}%")
    
    lines.append("\n--- Phase 1 vs Phase 3 Reconciliation ---")
    lines.append(f"Phase 1 overstatement total: ${reconciliation.get('phase1_overstate_dollar_total', 0):.2f}")
    lines.append(f"Avg overstatement/trade: ${reconciliation.get('avg_overstate_per_trade_dollar', 0):.4f}")
    
    return "\n".join(lines)
