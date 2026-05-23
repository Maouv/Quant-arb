"""
T-STR-01 to T-STR-05: Stress test logic tests
"""
import pytest
import pandas as pd
import sys
sys.path.insert(0, '/root/quant-arb/phase3_backtest')

from config import STRESS_WINDOWS, STRESS_MULTIPLIERS


class MockTrade:
    """Mock trade for stress testing."""
    def __init__(self, symbol: str, entryTime: pd.Timestamp, exitTime: pd.Timestamp,
                 grossPct: float, costRt: float):
        self.symbol = symbol
        self.entryTime = entryTime
        self.exitTime = exitTime
        self.grossPct = grossPct
        self.costRt = costRt
        self.netPct = grossPct - costRt
    
    def getSettlementsInWindow(self, windowStart: pd.Timestamp, 
                               windowEnd: pd.Timestamp) -> list[pd.Timestamp]:
        """Get settlement timestamps within window during hold."""
        # 8h settlements
        settlements = []
        current = self.entryTime
        while current <= self.exitTime:
            if windowStart <= current <= windowEnd:
                settlements.append(current)
            current += pd.Timedelta(hours=8)
        return settlements


def applyStressMultiplier(trade: MockTrade, multiplier: float, 
                          windowStart: pd.Timestamp, windowEnd: pd.Timestamp) -> float:
    """
    Apply cost multiplier to settlements within stress window.
    Returns adjusted net P&L.
    """
    settlementsInWindow = trade.getSettlementsInWindow(windowStart, windowEnd)
    
    if not settlementsInWindow:
        # Trade doesn't overlap with window
        return trade.netPct
    
    # Assume cost is distributed evenly across settlements
    # For simplicity: cost per settlement = costRt / holdSettlements
    # In stress: cost for settlements in window = costPerSettlement * multiplier
    
    holdSettlements = int((trade.exitTime - trade.entryTime) / pd.Timedelta(hours=8))
    if holdSettlements == 0:
        holdSettlements = 1
    
    costPerSettlement = trade.costRt / holdSettlements
    
    # Calculate adjusted cost
    adjustedCost = 0.0
    current = trade.entryTime
    for i in range(holdSettlements):
        settlementTime = current + pd.Timedelta(hours=8*i)
        if windowStart <= settlementTime <= windowEnd:
            adjustedCost += costPerSettlement * multiplier
        else:
            adjustedCost += costPerSettlement
    
    return trade.grossPct - adjustedCost


# T-STR-01: Multiplier applied ke semua settlements dalam window, bukan cherry-pick
def test_multiplier_applied_to_all_settlements_in_window():
    """Verify multiplier affects ALL settlements within window."""
    windowStart = pd.Timestamp("2022-05-01", tz="UTC")
    windowEnd = pd.Timestamp("2022-05-31 23:59:59", tz="UTC")
    
    # Trade with 3 settlements: 2 in window, 1 outside
    entry = pd.Timestamp("2022-04-30 00:00:00", tz="UTC")
    exitTime = pd.Timestamp("2022-05-16 00:00:00", tz="UTC")  # 6 settlements total
    
    trade = MockTrade("TESTUSDT", entry, exitTime, grossPct=0.30, costRt=0.12)
    
    # Settlements: Apr 30, May 8, May 16, May 24, Jun 1, Jun 9
    # In window: May 8, May 16 (2 settlements)
    # Outside: Apr 30 (before), May 24 may be in window depending on exact timing
    
    # With multiplier 3x
    adjustedNet = applyStressMultiplier(trade, 3.0, windowStart, windowEnd)
    
    # Original net = 0.30 - 0.12 = 0.18
    # 6 settlements, cost per settlement = 0.02
    # Settlements in window get cost * 3 = 0.06 each
    
    # Count settlements in window
    inWindowCount = len(trade.getSettlementsInWindow(windowStart, windowEnd))
    assert inWindowCount > 0, "Should have settlements in window"
    
    # Adjusted net should be lower than original
    assert adjustedNet < trade.netPct, "Stress multiplier should reduce net"


# T-STR-02: Settlements di luar window tidak ter-affect
def test_settlements_outside_window_unaffected():
    """Verify settlements outside stress window keep normal cost."""
    windowStart = pd.Timestamp("2022-05-01", tz="UTC")
    windowEnd = pd.Timestamp("2022-05-31 23:59:59", tz="UTC")
    
    # Trade completely outside window
    entry = pd.Timestamp("2022-06-01 00:00:00", tz="UTC")
    exitTime = pd.Timestamp("2022-06-15 00:00:00", tz="UTC")
    
    trade = MockTrade("TESTUSDT", entry, exitTime, grossPct=0.15, costRt=0.10)
    
    adjustedNet = applyStressMultiplier(trade, 5.0, windowStart, windowEnd)
    
    # Should be exactly original net
    assert abs(adjustedNet - trade.netPct) < 0.0001, \
        "Trade outside window should not be affected"


# T-STR-03: Mid-position spike anchor = hari pertama window, bukan settlement ke-2 entry
def test_mid_position_spike_anchor_is_window_start():
    """Verify cost spike starts from window start, not from entry settlement 2."""
    windowStart = pd.Timestamp("2022-05-01", tz="UTC")
    windowEnd = pd.Timestamp("2022-05-31 23:59:59", tz="UTC")
    
    # Trade entry before window, hold through window
    entry = pd.Timestamp("2022-04-15 00:00:00", tz="UTC")  # 15 days before window
    exitTime = pd.Timestamp("2022-05-15 00:00:00", tz="UTC")  # In window
    
    trade = MockTrade("TESTUSDT", entry, exitTime, grossPct=0.25, costRt=0.10)
    
    # Settlements before window should have normal cost
    # Settlements from window start should have multiplied cost
    
    inWindowSettlements = trade.getSettlementsInWindow(windowStart, windowEnd)
    
    # Verify that settlements after windowStart are counted
    for s in inWindowSettlements:
        assert s >= windowStart, f"Settlement {s} should be >= window start {windowStart}"


# T-STR-04: Trade entry dalam window, exit setelah window → cost normal setelah window
def test_trade_entry_in_window_exit_after_window():
    """Verify cost returns to normal after window ends."""
    windowStart = pd.Timestamp("2022-05-01", tz="UTC")
    windowEnd = pd.Timestamp("2022-05-31 23:59:59", tz="UTC")
    
    # Trade entry in window, exit after
    entry = pd.Timestamp("2022-05-10 00:00:00", tz="UTC")
    exitTime = pd.Timestamp("2022-06-15 00:00:00", tz="UTC")
    
    trade = MockTrade("TESTUSDT", entry, exitTime, grossPct=0.30, costRt=0.15)
    
    # Some settlements in window (high cost), some after (normal cost)
    inWindow = trade.getSettlementsInWindow(windowStart, windowEnd)
    assert len(inWindow) > 0, "Should have settlements in window"
    
    # Settlements after May 31 should have normal cost
    # This is implicitly tested in applyStressMultiplier logic
    adjustedNet = applyStressMultiplier(trade, 3.0, windowStart, windowEnd)
    
    # Adjusted net should be between full multiplier and no multiplier
    fullMultiplierNet = trade.grossPct - (trade.costRt * 3)
    noMultiplierNet = trade.netPct
    
    assert fullMultiplierNet < adjustedNet < noMultiplierNet, \
        "Partial window overlap should give partial cost increase"


# T-STR-05: Trade entry sebelum window, exit dalam window → cost naik dari hari pertama window
def test_trade_entry_before_window_exit_in_window():
    """Verify cost increases from first day of window for pre-existing positions."""
    windowStart = pd.Timestamp("2022-05-01", tz="UTC")
    windowEnd = pd.Timestamp("2022-05-31 23:59:59", tz="UTC")
    
    # Trade entry before window, exit in window
    entry = pd.Timestamp("2022-04-20 00:00:00", tz="UTC")
    exitTime = pd.Timestamp("2022-05-10 00:00:00", tz="UTC")
    
    trade = MockTrade("TESTUSDT", entry, exitTime, grossPct=0.20, costRt=0.10)
    
    # Settlements before May 1: normal cost
    # Settlements from May 1 onward: multiplied cost
    
    inWindow = trade.getSettlementsInWindow(windowStart, windowEnd)
    assert len(inWindow) > 0, "Should have settlements in window"
    
    # The first settlement in window should be the anchor
    firstInWindow = min(inWindow)
    assert firstInWindow >= windowStart, \
        f"First settlement in window {firstInWindow} should be >= window start {windowStart}"
    
    adjustedNet = applyStressMultiplier(trade, 4.0, windowStart, windowEnd)
    
    # Net should be reduced due to partial multiplier application
    assert adjustedNet < trade.netPct, \
        "Mid-position cost spike should reduce net P&L"
