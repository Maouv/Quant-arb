"""
Phase 3 Backtest Entrypoint
"""
import argparse
import logging
import os
import sys
from pathlib import Path
import pandas as pd

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from config import DATA_PATH, COST_TIERS
from engine.data_loader import loadAllFundingRates
from engine.simulator import runSimulation
from analysis.monthly import calculateMonthlyStats, flagAnomalousMonths, formatMonthlyReport
from analysis.stress_test import runStressTest, analyzeRecovery, formatStressReport
from analysis.drawdown import (
    calculateDrawdownMetrics, calculateConsecutiveLosses,
    analyzeShortHoldFragility, calculatePhase1Reconciliation, formatDrawdownReport
)
from analysis.decay_validator import validateDecayModel, formatDecayReport

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def runBacktest(tier: str) -> dict:
    """
    Run full backtest with given cost tier.
    
    Args:
        tier: Cost tier ("low", "mid", "high")
    
    Returns:
        Dict with all results
    """
    logger.info(f"Starting backtest with tier={tier}")
    
    # Load data
    logger.info("Loading funding rate data...")
    frData = loadAllFundingRates(DATA_PATH)
    
    if not frData:
        logger.error("No valid FR data found")
        return {}
    
    logger.info(f"Loaded {len(frData)} symbols")
    
    # Run simulation
    logger.info("Running simulation...")
    sim = runSimulation(frData, tier=tier)
    
    # Get results
    tradeLog = sim.getTradeLog()
    equityCurve = sim.getEquityCurve()
    
    logger.info(f"Simulation complete: {len(tradeLog)} trades")
    
    # Run analyses
    logger.info("Running analyses...")
    
    # Monthly stats
    monthlyStats = calculateMonthlyStats(tradeLog)
    monthlyStats = flagAnomalousMonths(monthlyStats)
    
    # Stress tests
    stressResults = {}
    for windowName, (windowStart, windowEnd) in {
        "LUNA": ("2022-05-01", "2022-05-31"),
        "FTX": ("2022-11-01", "2022-11-30"),
        "BTC": ("2024-08-01", "2024-08-31"),
    }.items():
        stressResults[windowName] = runStressTest(
            tradeLog, windowName, windowStart, windowEnd
        )
        stressResults[windowName]["recovery"] = analyzeRecovery(
            tradeLog, windowEnd
        )
    
    # Drawdown
    ddMetrics = calculateDrawdownMetrics(equityCurve)
    consecMetrics = calculateConsecutiveLosses(tradeLog)
    shortHold = analyzeShortHoldFragility(tradeLog)
    reconciliation = calculatePhase1Reconciliation(tradeLog)
    
    # Decay validation
    decayDf = validateDecayModel(tradeLog)
    
    return {
        "tier": tier,
        "trade_log": tradeLog,
        "equity_curve": equityCurve,
        "monthly_stats": monthlyStats,
        "stress_results": stressResults,
        "drawdown_metrics": ddMetrics,
        "consecutive_metrics": consecMetrics,
        "short_hold": shortHold,
        "reconciliation": reconciliation,
        "decay_validation": decayDf,
    }


def saveResults(results: dict, outputDir: str = "results") -> None:
    """
    Save backtest results to files.
    
    Args:
        results: Results dict from runBacktest
        outputDir: Output directory
    """
    tier = results["tier"]
    
    # Create output directory
    os.makedirs(outputDir, exist_ok=True)
    
    # Save trade log
    tradeDf = pd.DataFrame(results["trade_log"])
    if not tradeDf.empty:
        tradeDf.to_csv(f"{outputDir}/trade_log_{tier}.csv", index=False)
        logger.info(f"Saved trade log: {outputDir}/trade_log_{tier}.csv")
    
    # Save equity curve
    equityDf = results["equity_curve"]
    if not equityDf.empty:
        equityDf.to_csv(f"{outputDir}/equity_curve_{tier}.csv", index=False)
        logger.info(f"Saved equity curve: {outputDir}/equity_curve_{tier}.csv")
    
    # Generate and save report
    report = generateReport(results)
    with open(f"{outputDir}/report_{tier}.txt", "w") as f:
        f.write(report)
    logger.info(f"Saved report: {outputDir}/report_{tier}.txt")


def generateReport(results: dict) -> str:
    """
    Generate comprehensive text report.
    
    Args:
        results: Results dict from runBacktest
    
    Returns:
        Formatted text report
    """
    lines = [
        "=" * 70,
        "PHASE 3 BACKTEST REPORT",
        f"Cost Tier: {results['tier'].upper()}",
        "=" * 70,
        "",
    ]
    
    # Summary
    tradeLog = results["trade_log"]
    if tradeLog:
        totalTrades = len(tradeLog)
        totalPnl = sum(t["net_dollar"] for t in tradeLog)
        winRate = sum(1 for t in tradeLog if t["net_pct"] > 0) / totalTrades * 100
        avgHold = sum(t["hold_settlements"] for t in tradeLog) / totalTrades
        
        lines.append("--- SUMMARY ---")
        lines.append(f"Total trades: {totalTrades}")
        lines.append(f"Total P&L: ${totalPnl:.2f}")
        lines.append(f"Win rate: {winRate:.1f}%")
        lines.append(f"Avg hold: {avgHold:.1f} settlements")
        lines.append("")
    
    # Monthly stats
    if not results["monthly_stats"].empty:
        lines.append(formatMonthlyReport(results["monthly_stats"]))
        lines.append("")
    
    # Drawdown
    lines.append(formatDrawdownReport(
        results["drawdown_metrics"],
        results["consecutive_metrics"],
        results["short_hold"],
        results["reconciliation"]
    ))
    lines.append("")
    
    # Decay validation
    if not results["decay_validation"].empty:
        lines.append(formatDecayReport(results["decay_validation"]))
        lines.append("")
    
    # Stress tests
    for windowName, stressData in results["stress_results"].items():
        lines.append(formatStressReport(stressData, stressData.get("recovery", {})))
        lines.append("")
    
    return "\n".join(lines)


def main():
    """Main entrypoint."""
    parser = argparse.ArgumentParser(
        description="Phase 3 Funding Rate Arbitrage Backtest"
    )
    parser.add_argument(
        "--tier",
        choices=["low", "mid", "high"],
        required=True,
        help="Cost tier for symbols without actual Phase 0 costs"
    )
    parser.add_argument(
        "--output-dir",
        default="results",
        help="Output directory for results (default: results)"
    )
    
    args = parser.parse_args()
    
    # Run backtest
    results = runBacktest(args.tier)
    
    if not results:
        logger.error("Backtest failed")
        sys.exit(1)
    
    # Save results
    saveResults(results, outputDir=args.output_dir)
    
    # Print summary
    print(generateReport(results))


if __name__ == "__main__":
    main()
