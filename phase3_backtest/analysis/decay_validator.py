"""
Decay model validation: predicted vs actual gross per hold bucket.
"""
import pandas as pd
import sys
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DECAY_RATIO


def predictGross(entryFr: float, holdSettlements: int, 
                  decayRatio: float = DECAY_RATIO) -> float:
    """
    Predict gross using geometric decay model.
    
    Formula: gross = FR_entry * (1 - d^n) / (1 - d)
    where d = decay ratio, n = hold settlements
    
    Args:
        entryFr: FR at entry signal (%)
        holdSettlements: Number of settlements held
        decayRatio: Decay ratio per settlement
    
    Returns:
        Predicted gross yield (%)
    """
    if holdSettlements <= 0:
        return 0.0
    
    n = holdSettlements
    d = decayRatio
    
    # Geometric series sum: FR * (1 - d^n) / (1 - d)
    gross = abs(entryFr) * (1 - d**n) / (1 - d)
    return gross


def bucketByHold(tradeLog: list[dict]) -> dict[str, list[dict]]:
    """
    Bucket trades by hold length.
    
    Buckets:
    - hold = 1
    - hold = 2
    - hold = 3
    - hold = 4-6
    - hold = 7-10
    - hold = 11+
    
    Args:
        tradeLog: List of trade dicts
    
    Returns:
        Dict mapping bucket name -> trades
    """
    buckets = {
        "hold_1": [],
        "hold_2": [],
        "hold_3": [],
        "hold_4_6": [],
        "hold_7_10": [],
        "hold_11_plus": [],
    }
    
    for trade in tradeLog:
        hold = trade["hold_settlements"]
        
        if hold == 1:
            buckets["hold_1"].append(trade)
        elif hold == 2:
            buckets["hold_2"].append(trade)
        elif hold == 3:
            buckets["hold_3"].append(trade)
        elif 4 <= hold <= 6:
            buckets["hold_4_6"].append(trade)
        elif 7 <= hold <= 10:
            buckets["hold_7_10"].append(trade)
        else:
            buckets["hold_11_plus"].append(trade)
    
    return buckets


def validateDecayModel(tradeLog: list[dict]) -> pd.DataFrame:
    """
    Compare predicted vs actual gross per hold bucket.
    
    Args:
        tradeLog: List of trade dicts
    
    Returns:
        DataFrame with validation results
    """
    buckets = bucketByHold(tradeLog)
    
    results = []
    
    for bucketName, trades in buckets.items():
        if not trades:
            continue
        
        actualGrossList = []
        predictedGrossList = []
        
        for trade in trades:
            actualGross = trade["gross_pct"]
            predictedGross = predictGross(
                entryFr=trade["entry_fr"],
                holdSettlements=trade["hold_settlements"],
            )
            
            actualGrossList.append(actualGross)
            predictedGrossList.append(predictedGross)
        
        avgActual = sum(actualGrossList) / len(actualGrossList)
        avgPredicted = sum(predictedGrossList) / len(predictedGrossList)
        gap = avgActual - avgPredicted
        gapPct = (gap / avgPredicted * 100) if avgPredicted != 0 else 0
        
        results.append({
            "bucket": bucketName,
            "trades": len(trades),
            "predicted_gross_pct": avgPredicted,
            "actual_gross_pct": avgActual,
            "gap_pct": gap,
            "gap_pct_of_predicted": gapPct,
        })
    
    return pd.DataFrame(results)


def formatDecayReport(decayDf: pd.DataFrame) -> str:
    """
    Format decay validation as text report.
    
    Args:
        decayDf: DataFrame from validateDecayModel
    
    Returns:
        Formatted text report
    """
    if decayDf.empty:
        return "No trades to analyze."
    
    lines = ["=== DECAY MODEL VALIDATION ===\n"]
    lines.append(f"{'Bucket':<15} {'Trades':>8} {'Predicted%':>12} {'Actual%':>10} {'Gap%':>10}")
    lines.append("-" * 60)
    
    for _, row in decayDf.iterrows():
        lines.append(
            f"{row['bucket']:<15} {row['trades']:>8} "
            f"{row['predicted_gross_pct']:>11.4f}% {row['actual_gross_pct']:>9.4f}% "
            f"{row['gap_pct']:>9.4f}%"
        )
    
    return "\n".join(lines)
