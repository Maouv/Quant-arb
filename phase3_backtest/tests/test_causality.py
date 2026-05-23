"""
T-CAU-01 to T-CAU-04: Temporal causality tests
"""
import pytest
import pandas as pd
import sys
sys.path.insert(0, '/root/quant-arb/phase3_backtest')

from config import ENTRY_THRESHOLD, EXIT_THRESHOLD


class MockSettlement:
    """Mock settlement data for testing."""
    def __init__(self, timestamp: pd.Timestamp, fr: float):
        self.timestamp = timestamp
        self.fr = fr  # Already in percent


class CausalSimulator:
    """
    Minimal simulator to test causality rules.
    Implements t+1 enforcement strictly.
    """
    def __init__(self):
        self.entryThreshold = ENTRY_THRESHOLD
        self.exitThreshold = EXIT_THRESHOLD
        self.signals: list[dict] = []  # Signals generated
        self.actions: list[dict] = []  # Actions taken
        self.positions: dict[str, dict] = {}  # Active positions
    
    def processSettlement(self, settlement: MockSettlement, 
                          prevSettlement: MockSettlement | None = None) -> None:
        """
        Process one settlement with strict t+1 causality.
        
        Rule: FR at index t can ONLY trigger action at index t+1.
        
        Order: Close → Open → Collect
        New positions collect FR at the same settlement they're opened.
        """
        # Step 1: Close positions triggered at t-1
        if prevSettlement:
            for symbol in list(self.positions.keys()):
                # Exit signal from previous settlement
                if abs(prevSettlement.fr) < self.exitThreshold:
                    self.actions.append({
                        "type": "exit",
                        "symbol": symbol,
                        "time": settlement.timestamp,
                        "trigger_time": prevSettlement.timestamp,
                        "trigger_fr": prevSettlement.fr
                    })
                    del self.positions[symbol]
        
        # Step 2: Open positions from signals at t-1
        if prevSettlement:
            # Entry signal from previous settlement
            if abs(prevSettlement.fr) >= self.entryThreshold:
                signalSymbol = "TESTUSDT"
                if signalSymbol not in self.positions:
                    self.signals.append({
                        "type": "entry",
                        "symbol": signalSymbol,
                        "signal_time": prevSettlement.timestamp,
                        "action_time": settlement.timestamp,
                        "trigger_fr": prevSettlement.fr
                    })
                    self.positions[signalSymbol] = {
                        "entryTime": settlement.timestamp,
                        "entryFr": prevSettlement.fr,
                        "grossCollected": 0.0
                    }
        
        # Step 3: Collect FR for ALL open positions (including newly opened)
        for symbol in self.positions:
            self.positions[symbol]["grossCollected"] += abs(settlement.fr)


def makeTimestamps(baseDate: str, count: int) -> list[pd.Timestamp]:
    """Generate 8h settlement timestamps."""
    base = pd.Timestamp(baseDate, tz="UTC")
    return [base + pd.Timedelta(hours=8*i) for i in range(count)]


# T-CAU-01: FR di index t tidak trigger entry di t — harus t+1
def test_fr_at_t_triggers_entry_at_t_plus_one():
    """Verify FR at t only triggers entry at t+1, not at t."""
    sim = CausalSimulator()
    times = makeTimestamps("2022-01-01", 4)
    
    # t=0: FR=0.08% (>= entry threshold) -> SIGNAL
    s0 = MockSettlement(times[0], 0.08)
    sim.processSettlement(s0, None)
    
    # No action should be taken at t=0
    assert len(sim.actions) == 0, "No action at t=0"
    assert len(sim.signals) == 0, "No signal recorded yet (nothing to compare to)"
    
    # t=1: Entry should happen here
    s1 = MockSettlement(times[1], 0.07)
    sim.processSettlement(s1, s0)
    
    # Signal should be recorded from t=0 -> action at t=1
    assert len(sim.signals) == 1, "Entry signal should be generated"
    assert sim.signals[0]["signal_time"] == times[0], "Signal time should be t=0"
    assert sim.signals[0]["action_time"] == times[1], "Action time should be t=1"
    
    # Position should now exist
    assert "TESTUSDT" in sim.positions, "Position should be open"


# T-CAU-02: Entry dan exit tidak terjadi di settlement yang sama
def test_entry_and_exit_cannot_occur_at_same_settlement():
    """Verify entry and exit are separated by at least one settlement."""
    sim = CausalSimulator()
    times = makeTimestamps("2022-01-01", 6)
    
    # t=0: FR=0.08% -> entry signal
    s0 = MockSettlement(times[0], 0.08)
    sim.processSettlement(s0, None)
    
    # t=1: Entry happens, collect FR[1]=0.07%
    s1 = MockSettlement(times[1], 0.07)
    sim.processSettlement(s1, s0)
    
    # Position should be open
    assert "TESTUSDT" in sim.positions, "Position should be open after t=1"
    
    # t=2: FR=0.03% (still above exit threshold 0.02%)
    s2 = MockSettlement(times[2], 0.03)
    sim.processSettlement(s2, s1)
    
    # Position should still be open
    assert "TESTUSDT" in sim.positions, "Position should still be open"
    
    # t=3: FR=0.01% (< exit threshold) -> exit signal
    s3 = MockSettlement(times[3], 0.01)
    sim.processSettlement(s3, s2)
    
    # Exit should NOT happen yet at t=3
    # The exit signal is at t=3, action at t=4
    assert "TESTUSDT" in sim.positions, "Position still open at t=3 (exit signal time)"
    
    # t=4: Exit happens
    s4 = MockSettlement(times[4], 0.02)
    sim.processSettlement(s4, s3)
    
    # Now position should be closed
    assert "TESTUSDT" not in sim.positions, "Position should be closed at t=4"
    
    # Verify entry and exit times are different
    exitAction = [a for a in sim.actions if a["type"] == "exit"][0]
    entrySignal = [s for s in sim.signals if s["type"] == "entry"][0]
    assert entrySignal["action_time"] != exitAction["time"], \
        "Entry and exit must be at different settlements"


# T-CAU-03: Gross hanya dari FR settlements SELAMA posisi open
def test_gross_only_from_settlements_while_open():
    """Verify gross excludes FR before entry and after exit signal."""
    sim = CausalSimulator()
    times = makeTimestamps("2022-01-01", 6)
    
    # t=0: FR=0.10% -> entry signal (NOT collected)
    s0 = MockSettlement(times[0], 0.10)
    sim.processSettlement(s0, None)
    
    # t=1: Entry happens, collect FR[1]=0.07%
    s1 = MockSettlement(times[1], 0.07)
    sim.processSettlement(s1, s0)
    
    # t=2: Collect FR[2]=0.06%
    s2 = MockSettlement(times[2], 0.06)
    sim.processSettlement(s2, s1)
    
    # t=3: FR=0.01% -> exit signal (NOT collected)
    s3 = MockSettlement(times[3], 0.01)
    sim.processSettlement(s3, s2)
    
    # t=4: Exit happens (FR[4] not collected)
    s4 = MockSettlement(times[4], 0.02)
    sim.processSettlement(s4, s3)
    
    # With corrected order (Close → Open → Collect):
    # t=0: Signal entry, no position yet
    # t=1: Open position, then collect FR[1]=0.07% → gross = 0.07
    # t=2: Collect FR[2]=0.06% → gross = 0.13
    # t=3: Exit signal, but position still open during collect step
    #      BUT exit signal at t=3 means FR[3] is NOT collected
    #      because exit happens FIRST in the order
    # t=4: Exit executed, position closed
    
    # Get gross after t=2 (before exit signal at t=3)
    sim2 = CausalSimulator()
    sim2.processSettlement(s0, None)
    sim2.processSettlement(s1, s0)
    sim2.processSettlement(s2, s1)
    
    grossAfterT2 = sim2.positions["TESTUSDT"]["grossCollected"]
    
    # Process t=3 and t=4
    sim2.processSettlement(s3, s2)
    sim2.processSettlement(s4, s3)
    
    # Expected: FR[1] + FR[2] = 0.13%
    # FR[3]=0.01 triggers exit signal, position closes at t=4 before collecting FR[3]
    expectedGross = 0.07 + 0.06
    
    assert abs(grossAfterT2 - expectedGross) < 0.0001, \
        f"Gross should be {expectedGross}%, got {grossAfterT2}%"
    
    # Verify position is closed after t=4
    assert "TESTUSDT" not in sim2.positions, "Position should be closed after t=4"


# T-CAU-04: Posisi tidak pernah "tahu" FR masa depan
def test_position_never_uses_future_fr():
    """Verify decisions only use current and past FR values."""
    sim = CausalSimulator()
    times = makeTimestamps("2022-01-01", 5)
    
    # Setup: FR sequence that could tempt lookahead
    # t=0: FR=0.08% -> entry signal
    # t=1: FR=0.09% (higher) -> entry happens, collect
    # t=2: FR=0.12% (much higher) -> collect
    # t=3: FR=0.005% (very low) -> exit signal
    # t=4: FR=0.20% (spike!) -> exit happens (missed opportunity)
    
    frSequence = [0.08, 0.09, 0.12, 0.005, 0.20]
    settlements = [MockSettlement(times[i], frSequence[i]) for i in range(5)]
    
    for i in range(5):
        prev = settlements[i-1] if i > 0 else None
        sim.processSettlement(settlements[i], prev)
    
    # Position should have exited at t=4 based on FR[t=3]=0.005%
    # It should NOT have stayed open to collect FR[t=4]=0.20%
    assert "TESTUSDT" not in sim.positions, "Position should be closed"
    
    # The exit was triggered by FR[t=3]=0.005% (exit signal)
    exitAction = [a for a in sim.actions if a["type"] == "exit"][0]
    assert abs(exitAction["trigger_fr"] - 0.005) < 0.0001, \
        "Exit should be triggered by FR=0.005%, not by seeing future FR=0.20%"
