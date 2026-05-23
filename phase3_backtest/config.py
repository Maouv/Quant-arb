"""
Phase 3 Backtest Configuration
All parameters for funding rate arbitrage simulation.
"""

import os as _os
# --- Data ---
DATA_PATH: str = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "funding_rate_data_8h_expanded")
TRAINING_START: str = "2022-01-01"
TRAINING_END: str = "2024-12-31"
MIN_TRAINING_MONTHS: int = 18
EXCLUDED_SYMBOLS: list[str] = ["NEARUSDT"]

# --- Strategy ---
ENTRY_THRESHOLD: float = 0.05   # % per settlement, |FR| >= ini untuk entry signal
EXIT_THRESHOLD: float = 0.02    # % per settlement, |FR| < ini untuk exit signal

# --- Portfolio ---
TOTAL_CAPITAL: float = 3000.0
BUFFER_RATIO: float = 0.40
MAX_PAIRS: int = 6
EFFECTIVE_CAPITAL: float = TOTAL_CAPITAL * (1 - BUFFER_RATIO)  # 1800.0
SIZE_PER_PAIR: float = EFFECTIVE_CAPITAL / MAX_PAIRS  # 300.0

# --- Cost Model ---
ACTUAL_COSTS: dict[str, float] = {
    "ETHUSDT":  0.0814,
    "ZECUSDT":  0.0882,
    "XRPUSDT":  0.1018,
    "DOGEUSDT": 0.1088,
    "LINKUSDT": 0.1113,
    "SUIUSDT":  0.1119,
    "AAVEUSDT": 0.1275,
    "INJUSDT":  0.1562,
    "UNIUSDT":  0.1773,
    "ADAUSDT":  0.2002,
}

COST_TIERS: dict[str, float] = {"low": 0.08, "mid": 0.12, "high": 0.20}

# --- Stress Test ---
STRESS_MULTIPLIERS: list[int] = [2, 3, 4, 5, 6]
STRESS_WINDOWS: dict[str, tuple[str, str]] = {
    "LUNA": ("2022-05-01", "2022-05-31"),
    "FTX":  ("2022-11-01", "2022-11-30"),
    "BTC":  ("2024-08-01", "2024-08-31"),
}
RECOVERY_DAYS: int = 90

# --- Decay Model ---
DECAY_RATIO: float = 0.777  # median decay per settlement

# --- Fragility Analysis ---
SHORT_HOLD_THRESHOLD: int = 3  # settlements
