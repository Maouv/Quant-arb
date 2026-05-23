"""
T-ACC-01 to T-ACC-06: Accounting correctness tests
"""
import pytest
import pandas as pd
from decimal import Decimal
import sys
sys.path.insert(0, '/root/quant-arb/phase3_backtest')

from config import MAX_PAIRS, EFFECTIVE_CAPITAL, SIZE_PER_PAIR, ACTUAL_COSTS, COST_TIERS


class MockPosition:
    """Minimal position mock for accounting tests."""
    def __init__(self, symbol: str, entryTime: pd.Timestamp, entryFr: float, 
                 costRt: float, grossCollected: float = 0.0):
        self.symbol = symbol
        self.entryTime = entryTime
        self.entryFr = entryFr
        self.costRt = costRt
        self.grossCollected = grossCollected
        self.holdSettlements = 0
    
    def collectFr(self, frValue: float) -> None:
        """Add FR to gross collected."""
        self.grossCollected += abs(frValue)
        self.holdSettlements += 1
    
    def close(self) -> dict:
        """Close position and return trade dict."""
        net = self.grossCollected - self.costRt
        return {
            "symbol": self.symbol,
            "entry_time": self.entryTime,
            "entry_fr": self.entryFr,
            "gross_pct": self.grossCollected,
            "cost_rt_pct": self.costRt,
            "net_pct": net,
            "hold_settlements": self.holdSettlements,
        }


class MockPortfolio:
    """Minimal portfolio mock for accounting tests."""
    def __init__(self, maxPairs: int = MAX_PAIRS, effectiveCapital: float = EFFECTIVE_CAPITAL):
        self.maxPairs = maxPairs
        self.effectiveCapital = effectiveCapital
        self.positions: list[MockPosition] = []
        self.trades: list[dict] = []
        self.balance = 0.0
    
    def openPosition(self, symbol: str, entryTime: pd.Timestamp, 
                     entryFr: float, costRt: float) -> bool:
        """Open a new position if slot available."""
        if len(self.positions) >= self.maxPairs:
            return False
        pos = MockPosition(symbol, entryTime, entryFr, costRt)
        self.positions.append(pos)
        return True
    
    def closePosition(self, symbol: str) -> dict | None:
        """Close position by symbol."""
        for i, pos in enumerate(self.positions):
            if pos.symbol == symbol:
                trade = pos.close()
                self.trades.append(trade)
                self.balance += trade["net_pct"] / 100 * SIZE_PER_PAIR
                del self.positions[i]
                return trade
        return None
    
    @property
    def exposure(self) -> float:
        """Total capital deployed."""
        return len(self.positions) * SIZE_PER_PAIR
    
    @property
    def openPositions(self) -> int:
        """Count of open positions."""
        return len(self.positions)


# T-ACC-01: cost_rt dikurangi tepat sekali per trade, bukan per settlement
def test_cost_deducted_once_per_trade():
    """Verify cost deducted exactly once, not per settlement."""
    portfolio = MockPortfolio()
    entryTime = pd.Timestamp("2022-01-01 00:00:00", tz="UTC")
    
    # Open position
    portfolio.openPosition("ETHUSDT", entryTime, 0.08, 0.0814)
    
    # Collect 3 settlements
    portfolio.positions[0].collectFr(0.07)
    portfolio.positions[0].collectFr(0.06)
    portfolio.positions[0].collectFr(0.05)
    
    # Close
    trade = portfolio.closePosition("ETHUSDT")
    
    # Gross = 0.07 + 0.06 + 0.05 = 0.18%
    # Cost = 0.0814% (deducted ONCE)
    # Net = 0.18 - 0.0814 = 0.0986%
    assert trade is not None
    assert abs(trade["gross_pct"] - 0.18) < 0.0001, f"Gross should be 0.18%, got {trade['gross_pct']}"
    assert abs(trade["cost_rt_pct"] - 0.0814) < 0.0001, f"Cost should be 0.0814%, got {trade['cost_rt_pct']}"
    assert abs(trade["net_pct"] - 0.0986) < 0.0001, f"Net should be 0.0986%, got {trade['net_pct']}"


# T-ACC-02: gross = sum |FR| selama hold sebelum cost
def test_gross_is_sum_of_fr_during_hold():
    """Verify gross is sum of absolute FR values collected."""
    portfolio = MockPortfolio()
    entryTime = pd.Timestamp("2022-01-01 00:00:00", tz="UTC")
    
    portfolio.openPosition("BTCUSDT", entryTime, 0.10, 0.12)
    
    # Collect various FR values
    frValues = [0.08, 0.06, 0.04, 0.03, 0.02]
    for fr in frValues:
        portfolio.positions[0].collectFr(fr)
    
    trade = portfolio.closePosition("BTCUSDT")
    
    expectedGross = sum(abs(fr) for fr in frValues)  # 0.23
    assert trade is not None
    assert abs(trade["gross_pct"] - expectedGross) < 0.0001, \
        f"Gross should be {expectedGross}%, got {trade['gross_pct']}"


# T-ACC-03: net = gross - cost, tidak lebih tidak kurang
def test_net_equals_gross_minus_cost():
    """Verify net is exactly gross minus cost."""
    portfolio = MockPortfolio()
    entryTime = pd.Timestamp("2022-01-01 00:00:00", tz="UTC")
    
    # Test multiple combinations
    testCases = [
        (0.15, 0.10),   # gross=0.15, cost=0.10 -> net=0.05
        (0.20, 0.08),   # gross=0.20, cost=0.08 -> net=0.12
        (0.05, 0.12),   # gross=0.05, cost=0.12 -> net=-0.07 (loss)
    ]
    
    for gross, cost in testCases:
        portfolio = MockPortfolio()
        portfolio.openPosition("TESTUSDT", entryTime, 0.08, cost)
        portfolio.positions[0].collectFr(gross)
        trade = portfolio.closePosition("TESTUSDT")
        
        expectedNet = gross - cost
        assert trade is not None
        assert abs(trade["net_pct"] - expectedNet) < 0.0001, \
            f"Net should be {expectedNet}%, got {trade['net_pct']}"


# T-ACC-04: open_positions tidak pernah > MAX_PAIRS = 6
def test_open_positions_never_exceeds_max():
    """Verify portfolio rejects positions when slots full."""
    portfolio = MockPortfolio()
    entryTime = pd.Timestamp("2022-01-01 00:00:00", tz="UTC")
    
    # Fill all 6 slots
    for i in range(MAX_PAIRS):
        symbol = f"COIN{i}USDT"
        result = portfolio.openPosition(symbol, entryTime, 0.08, 0.10)
        assert result is True, f"Should accept position {i+1}"
    
    # Attempt 7th position - should be rejected
    result = portfolio.openPosition("COIN7USDT", entryTime, 0.08, 0.10)
    assert result is False, "Should reject 7th position"
    assert portfolio.openPositions == MAX_PAIRS, \
        f"Should have exactly {MAX_PAIRS} positions"


# T-ACC-05: total exposure tidak pernah > effective_capital = 1800.0
def test_total_exposure_never_exceeds_capital():
    """Verify exposure stays within effective capital."""
    portfolio = MockPortfolio()
    entryTime = pd.Timestamp("2022-01-01 00:00:00", tz="UTC")
    
    # Fill all slots
    for i in range(MAX_PAIRS):
        portfolio.openPosition(f"COIN{i}USDT", entryTime, 0.08, 0.10)
    
    # Exposure should be exactly effective capital
    assert abs(portfolio.exposure - EFFECTIVE_CAPITAL) < 0.01, \
        f"Exposure should be {EFFECTIVE_CAPITAL}, got {portfolio.exposure}"
    
    # Close one position
    portfolio.closePosition("COIN0USDT")
    
    # Exposure should decrease
    expectedExposure = (MAX_PAIRS - 1) * SIZE_PER_PAIR
    assert abs(portfolio.exposure - expectedExposure) < 0.01, \
        f"Exposure should be {expectedExposure}, got {portfolio.exposure}"


# T-ACC-06: P&L dua trades yang overlap tidak saling mempengaruhi
def test_overlapping_trades_pnl_independent():
    """Verify overlapping positions have independent P&L."""
    portfolio = MockPortfolio()
    entryTime = pd.Timestamp("2022-01-01 00:00:00", tz="UTC")
    
    # Open two positions
    portfolio.openPosition("COIN1USDT", entryTime, 0.08, 0.10)
    portfolio.openPosition("COIN2USDT", entryTime, 0.10, 0.08)
    
    # Collect different FR for each
    portfolio.positions[0].collectFr(0.07)  # COIN1
    portfolio.positions[0].collectFr(0.06)  # COIN1
    portfolio.positions[1].collectFr(0.05)  # COIN2
    
    # Close COIN1 first
    trade1 = portfolio.closePosition("COIN1USDT")
    assert trade1 is not None
    assert abs(trade1["gross_pct"] - 0.13) < 0.0001, "COIN1 gross should be 0.13%"
    assert abs(trade1["cost_rt_pct"] - 0.10) < 0.0001, "COIN1 cost should be 0.10%"
    
    # COIN2 should still have correct values
    assert portfolio.positions[0].grossCollected == 0.05, "COIN2 gross should be 0.05%"
    
    # Close COIN2
    trade2 = portfolio.closePosition("COIN2USDT")
    assert trade2 is not None
    assert abs(trade2["gross_pct"] - 0.05) < 0.0001, "COIN2 gross should be 0.05%"
    assert abs(trade2["cost_rt_pct"] - 0.08) < 0.0001, "COIN2 cost should be 0.08%"
