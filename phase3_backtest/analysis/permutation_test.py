"""
C1 — Permutation Null Test
Acak pasangan coin-FR di setiap settlement 100x, run backtest tiap permutation.
Tujuan: apakah profit $834 berasal dari strategy logic atau coin-FR pairing kebetulan?

NOTES on implementation:
- loadAllFundingRates() returns DataFrames with column 'fr_pct' (already *100, in %)
  NOT 'last_funding_rate'. Template had a bug here — corrected.
- Simulator API is runSimulation(frData, tier) not Simulator(data, costTier).
  Template had wrong constructor — corrected.
- Permutation shuffles coin labels at each settlement, preserving FR distribution
  but destroying coin identity → null hypothesis: profit is from coin-FR pairing.
"""
import numpy as np
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from engine.data_loader import loadAllFundingRates, buildMasterTimeline
from engine.simulator import runSimulation

N_PERMUTATIONS = 100
SEED_BASE = 42
TIER = "mid"
REAL_NET = 833.56  # results_v2 mid tier


def buildFrMatrix(allData: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Build matrix: rows=timestamps, cols=symbols, values=fr_pct.

    Args:
        allData: Dict from loadAllFundingRates (fr_pct already in %)

    Returns:
        DataFrame indexed by timestamp, columns=symbols
    """
    symbols = sorted(allData.keys())
    frames = {s: allData[s].set_index("timestamp")["fr_pct"] for s in symbols}
    matrix = pd.DataFrame(frames).sort_index()
    return matrix


def rebuildFrData(permutedMatrix: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Rebuild allData dict from permuted matrix for runSimulation.

    Args:
        permutedMatrix: Permuted FR matrix (fr_pct in %)

    Returns:
        Dict mapping symbol -> DataFrame with ['timestamp', 'fr_pct']
    """
    result = {}
    for symbol in permutedMatrix.columns:
        df = permutedMatrix[[symbol]].dropna().reset_index()
        df.columns = ["timestamp", "fr_pct"]
        result[symbol] = df
    return result


def runPermutation(matrix: pd.DataFrame, seed: int) -> float:
    """
    Permute FR values across coins at each settlement, return total net.

    At each timestep, shuffle which coin gets which FR value.
    This destroys coin identity while preserving the FR distribution.

    Args:
        matrix: FR matrix (rows=timestamps, cols=symbols, values=fr_pct)
        seed: RNG seed for reproducibility

    Returns:
        Total net dollar P&L of permuted backtest
    """
    rng = np.random.default_rng(seed)
    permuted = matrix.copy()

    for idx in range(len(matrix)):
        row = matrix.iloc[idx].values.copy()
        # Only permute non-NaN values
        mask = ~np.isnan(row)
        row[mask] = rng.permutation(row[mask])
        permuted.iloc[idx] = row

    permutedData = rebuildFrData(permuted)
    sim = runSimulation(permutedData, tier=TIER)
    trades = sim.getTradeLog()
    return sum(t["net_dollar"] for t in trades)


if __name__ == "__main__":
    outputDir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results_v2")
    os.makedirs(outputDir, exist_ok=True)

    print("Loading data...")
    allData = loadAllFundingRates()
    matrix = buildFrMatrix(allData)
    print(f"Matrix: {len(matrix)} settlements × {len(matrix.columns)} symbols")

    print(f"Running {N_PERMUTATIONS} permutations (tier={TIER})...")
    nullDist = []

    for i in range(N_PERMUTATIONS):
        net = runPermutation(matrix, seed=SEED_BASE + i)
        nullDist.append(net)
        print(f"  [{i+1:3d}/{N_PERMUTATIONS}] net = ${net:.2f}")

    nullDist = np.array(nullDist)
    percentile = (nullDist < REAL_NET).mean() * 100
    pValue = (nullDist >= REAL_NET).mean()

    print()
    print("=== C1 PERMUTATION TEST RESULTS ===")
    print(f"Real net:            ${REAL_NET:.2f}")
    print(f"Null mean:           ${nullDist.mean():.2f}")
    print(f"Null std:            ${nullDist.std():.2f}")
    print(f"Null p5:             ${np.percentile(nullDist, 5):.2f}")
    print(f"Null p50:            ${np.percentile(nullDist, 50):.2f}")
    print(f"Null p95:            ${np.percentile(nullDist, 95):.2f}")
    print(f"Real net percentile: {percentile:.1f}th")
    print(f"p-value:             {pValue:.4f}")
    print(f"Pass (p95+):         {'PASS' if percentile >= 95 else 'FAIL'}")

    # Save null distribution
    csvPath = os.path.join(outputDir, "permutation_null.csv")
    pd.DataFrame({"permutation_net": nullDist}).to_csv(csvPath, index=False)
    print(f"Saved to {csvPath}")

    # Save text report
    report = "\n".join([
        "=== C1 PERMUTATION TEST RESULTS ===",
        f"N permutations: {N_PERMUTATIONS}",
        f"Real net:            ${REAL_NET:.2f}",
        f"Null mean:           ${nullDist.mean():.2f}",
        f"Null std:            ${nullDist.std():.2f}",
        f"Null p5:             ${np.percentile(nullDist, 5):.2f}",
        f"Null p50:            ${np.percentile(nullDist, 50):.2f}",
        f"Null p95:            ${np.percentile(nullDist, 95):.2f}",
        f"Real net percentile: {percentile:.1f}th",
        f"p-value:             {pValue:.4f}",
        f"Pass (p95+):         {'PASS' if percentile >= 95 else 'FAIL'}",
    ])

    reportPath = os.path.join(outputDir, "permutation_test.txt")
    with open(reportPath, "w") as f:
        f.write(report)
    print(f"Saved to {reportPath}")
