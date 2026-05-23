"""
Statistical battery for Phase 3 backtest validation.
Tests B1-B4 on trade log to assess significance and robustness.
"""
import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ACTUAL_COSTS, COST_TIERS

ITERATIONS = 10_000
SEED = 42


def loadTrades(csvPath: str) -> pd.DataFrame:
    """Load and validate trade log CSV."""
    df = pd.read_csv(csvPath)
    required = ["net_dollar", "entry_time", "cost_tier", "cost_rt_pct", "gross_pct"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    df["entry_time"] = pd.to_datetime(df["entry_time"], format="mixed", utc=True)
    return df


def runB1TradeBootstrap(netDollar: np.ndarray, rng: np.random.Generator) -> dict:
    """
    B1: Trade-level bootstrap CI (10,000 iterations).
    Resample trades with replacement, compute total net each iteration.

    Args:
        netDollar: Array of per-trade net dollar P&L
        rng: Random number generator

    Returns:
        Dict with ci_lower, ci_upper, prob_negative
    """
    n = len(netDollar)
    totals = np.array([
        rng.choice(netDollar, size=n, replace=True).sum()
        for _ in range(ITERATIONS)
    ])
    ci = np.percentile(totals, [2.5, 97.5])
    probNeg = (totals < 0).mean()

    return {
        "ci_lower": float(ci[0]),
        "ci_upper": float(ci[1]),
        "prob_negative": float(probNeg),
        "pass": probNeg < 0.025,
    }


def runB2BlockBootstrap(df: pd.DataFrame, rng: np.random.Generator) -> dict:
    """
    B2: Block bootstrap by calendar month (10,000 iterations).
    Resample whole months with replacement.

    Args:
        df: Trade log DataFrame with entry_time and net_dollar
        rng: Random number generator

    Returns:
        Dict with ci_lower, ci_upper
    """
    df = df.copy()
    df["month"] = df["entry_time"].dt.to_period("M")
    months = df["month"].unique()
    monthlyTotals = df.groupby("month")["net_dollar"].sum().values
    n = len(monthlyTotals)

    totals = np.array([
        rng.choice(monthlyTotals, size=n, replace=True).sum()
        for _ in range(ITERATIONS)
    ])
    ci = np.percentile(totals, [2.5, 97.5])

    return {
        "ci_lower": float(ci[0]),
        "ci_upper": float(ci[1]),
        "months_sampled": n,
        "pass": float(ci[0]) > 0,
    }


def runB3SignRandomization(netDollar: np.ndarray, rng: np.random.Generator) -> dict:
    """
    B3: Sign randomization test (10,000 iterations).
    Under null hypothesis that signs are random, compute p-value.

    Args:
        netDollar: Array of per-trade net dollar P&L
        rng: Random number generator

    Returns:
        Dict with p_value
    """
    observed = netDollar.sum()
    absValues = np.abs(netDollar)
    n = len(absValues)

    # Randomly flip signs
    nullTotals = np.array([
        (absValues * rng.choice([-1, 1], size=n)).sum()
        for _ in range(ITERATIONS)
    ])

    # p-value: fraction of null totals >= observed
    pValue = float((nullTotals >= observed).mean())

    return {
        "observed_total": float(observed),
        "p_value": pValue,
        "pass": pValue < 0.01,
    }


def runB4CostGradient(df: pd.DataFrame) -> dict:
    """
    B4: Cost gradient analysis.
    For costs 0.06% to 0.26% step 0.02%, recompute total net
    replacing tier costs (non-'actual') with the test cost.

    Args:
        df: Trade log DataFrame

    Returns:
        Dict with results per cost level and break_even_cost
    """
    costRange = [round(c, 2) for c in np.arange(0.06, 0.27, 0.02)]
    results = {}
    breakEvenCost = None

    for testCost in costRange:
        adjustedNet = []
        for _, row in df.iterrows():
            if row["cost_tier"] == "actual":
                adjustedNet.append(row["net_dollar"])
            else:
                # Recompute: gross_pct / 100 * 300 - testCost / 100 * 300
                newNetDollar = (row["gross_pct"] - testCost) / 100 * 300.0
                adjustedNet.append(newNetDollar)

        totalNet = sum(adjustedNet)
        results[f"{testCost:.2f}"] = round(totalNet, 2)

        if breakEvenCost is None and totalNet < 0:
            breakEvenCost = round(testCost, 2)

    if breakEvenCost is None:
        breakEvenCost = costRange[-1]  # Still positive at max cost

    return {
        "cost_gradient": results,
        "break_even_cost": breakEvenCost,
        "pass": breakEvenCost >= 0.18,
    }


def formatReport(b1: dict, b2: dict, b3: dict, b4: dict,
                  tradeCount: int, totalNet: float) -> str:
    """Format battery results as text report."""
    lines = [
        "=" * 60,
        "PHASE 3 STATISTICAL BATTERY — results_v2/trade_log_mid.csv",
        "=" * 60,
        f"Trades analyzed: {tradeCount}",
        f"Total net (observed): ${totalNet:.2f}",
        f"Bootstrap iterations: {ITERATIONS:,}",
        "",
        "B1 — Trade Bootstrap CI (95%)",
        f"  CI lower:      ${b1['ci_lower']:.2f}",
        f"  CI upper:      ${b1['ci_upper']:.2f}",
        f"  prob_negative: {b1['prob_negative']:.4f}",
        f"  Pass (< 0.025): {'PASS' if b1['pass'] else 'FAIL'}",
        "",
        "B2 — Block Bootstrap by Month (95%)",
        f"  Months:    {b2['months_sampled']}",
        f"  CI lower:  ${b2['ci_lower']:.2f}",
        f"  CI upper:  ${b2['ci_upper']:.2f}",
        f"  Pass (lower > 0): {'PASS' if b2['pass'] else 'FAIL'}",
        "",
        "B3 — Sign Randomization",
        f"  Observed total: ${b3['observed_total']:.2f}",
        f"  p-value:        {b3['p_value']:.4f}",
        f"  Pass (< 0.01):  {'PASS' if b3['pass'] else 'FAIL'}",
        "",
        "B4 — Cost Gradient",
    ]

    for cost, net in b4["cost_gradient"].items():
        lines.append(f"  cost={cost}%: ${net:.2f}")

    lines += [
        f"  Break-even cost: {b4['break_even_cost']:.2f}%",
        f"  Pass (>= 0.18%): {'PASS' if b4['pass'] else 'FAIL'}",
        "",
        "=" * 60,
        "SUMMARY",
        "=" * 60,
        f"  B1: {'PASS' if b1['pass'] else 'FAIL'}",
        f"  B2: {'PASS' if b2['pass'] else 'FAIL'}",
        f"  B3: {'PASS' if b3['pass'] else 'FAIL'}",
        f"  B4: {'PASS' if b4['pass'] else 'FAIL'}",
        "",
        f"  Overall: {'ALL PASS' if all([b1['pass'], b2['pass'], b3['pass'], b4['pass']]) else 'SOME FAIL'}",
    ]

    return "\n".join(lines)


def runBattery(tradeCsvPath: str, outputPath: str) -> None:
    """
    Run full statistical battery and save results.

    Args:
        tradeCsvPath: Path to trade log CSV
        outputPath: Path to save text report
    """
    df = loadTrades(tradeCsvPath)
    netDollar = df["net_dollar"].values
    rng = np.random.default_rng(SEED)

    b1 = runB1TradeBootstrap(netDollar, rng)
    b2 = runB2BlockBootstrap(df, rng)
    b3 = runB3SignRandomization(netDollar, rng)
    b4 = runB4CostGradient(df)

    report = formatReport(b1, b2, b3, b4,
                           tradeCount=len(df),
                           totalNet=float(netDollar.sum()))

    Path(outputPath).parent.mkdir(parents=True, exist_ok=True)
    Path(outputPath).write_text(report)
    print(report)


if __name__ == "__main__":
    basePath = Path(__file__).parent.parent
    runBattery(
        tradeCsvPath=str(basePath / "results_v2" / "trade_log_mid.csv"),
        outputPath=str(basePath / "results_v2" / "statistical_battery.txt"),
    )
