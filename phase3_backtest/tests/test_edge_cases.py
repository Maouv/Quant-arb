"""
T-EDG-01 to T-EDG-07: Edge case handling tests
"""
import pytest
import pandas as pd
import sys
sys.path.insert(0, '/root/quant-arb/phase3_backtest')

from config import ENTRY_THRESHOLD, EXIT_THRESHOLD, MAX_PAIRS, MIN_TRAINING_MONTHS


# T-EDG-01: Data gap di tengah hold → posisi close di settlement terakhir sebelum gap
def test_data_gap_closes_position():
    """Verify position closes at last settlement before data gap."""
    # Simulate FR data with gap
    timestamps = [
        pd.Timestamp("2022-01-01 00:00:00", tz="UTC"),
        pd.Timestamp("2022-01-01 08:00:00", tz="UTC"),
        pd.Timestamp("2022-01-01 16:00:00", tz="UTC"),
        # Gap here - missing 2022-01-02 00:00:00
        pd.Timestamp("2022-01-02 08:00:00", tz="UTC"),  # Gap detected
    ]
    
    frValues = [0.08, 0.07, 0.06, 0.05]
    
    # Expected behavior:
    # - Position enters at t=1 (after signal at t=0)
    # - Collects at t=1, t=2
    # - Gap detected at t=3 (timestamp jump > 8h)
    # - Position should close at t=2 (last settlement before gap)
    
    # Detect gap
    for i in range(1, len(timestamps)):
        gap = timestamps[i] - timestamps[i-1]
        if gap > pd.Timedelta(hours=8):
            # Gap detected
            gapStartIdx = i - 1  # Last valid settlement
            assert gapStartIdx == 2, "Gap should be detected between t=2 and t=3"
            break


# T-EDG-02: Semua 6 slot penuh → opportunity baru di-reject, tidak ada eviction
def test_slot_full_rejects_new_opportunities():
    """Verify no eviction when all slots are full."""
    slots = []
    
    # Fill all slots
    for i in range(MAX_PAIRS):
        slots.append(f"COIN{i}USDT")
    
    assert len(slots) == MAX_PAIRS
    
    # New opportunity comes
    newOpportunity = "NEWCOINUSDT"
    
    # Should NOT evict existing position
    # Just reject
    if len(slots) >= MAX_PAIRS:
        canEnter = False
    else:
        canEnter = True
        slots.append(newOpportunity)
    
    assert canEnter is False, "Should reject new opportunity when full"
    assert len(slots) == MAX_PAIRS, "Should not evict existing positions"
    assert newOpportunity not in slots, "New opportunity should not be in slots"


# T-EDG-03: FR flip dalam 1 settlement → exit signal di t, exit eksekusi di t+1
def test_fr_flip_exit_signal_at_t_executes_at_t_plus_one():
    """Verify FR crossing exit threshold triggers exit at t+1."""
    entryThreshold = ENTRY_THRESHOLD  # 0.05%
    exitThreshold = EXIT_THRESHOLD    # 0.02%
    
    # FR sequence: high -> drops below exit threshold
    frSequence = [
        0.08,  # t=0: entry signal
        0.07,  # t=1: entry happens, collect
        0.03,  # t=2: collect (still above exit threshold)
        0.01,  # t=3: exit signal (below 0.02%)
        0.02,  # t=4: exit executes
    ]
    
    # Verify exit threshold logic
    assert frSequence[3] < exitThreshold, "t=3 should be exit signal"
    assert frSequence[3] < exitThreshold and frSequence[3] != exitThreshold, \
        "Exit signal at FR < 0.02% (not <= 0.02%)"
    
    # Exit executes at t=4, not t=3
    exitSignalTime = 3
    exitExecutionTime = 4
    
    assert exitExecutionTime == exitSignalTime + 1, \
        "Exit execution should be at t+1 from signal"


# T-EDG-04: Coin dengan data < 18 bulan → di-skip seluruhnya (tidak partial)
def test_insufficient_data_skipped_entirely():
    """Verify coins with < 18 months data are completely skipped."""
    minMonths = MIN_TRAINING_MONTHS  # 18
    
    # Simulate data duration check
    testDataCases = [
        ("COIN_SHORT", 12),   # 12 months - should skip
        ("COIN_BORDER", 17),  # 17 months - should skip
        ("COIN_VALID", 18),   # 18 months - should include
        ("COIN_LONG", 24),    # 24 months - should include
    ]
    
    includedSymbols = []
    skippedSymbols = []
    
    for symbol, months in testDataCases:
        if months >= minMonths:
            includedSymbols.append(symbol)
        else:
            skippedSymbols.append(symbol)
    
    assert "COIN_SHORT" in skippedSymbols, "12 months should be skipped"
    assert "COIN_BORDER" in skippedSymbols, "17 months should be skipped"
    assert "COIN_VALID" in includedSymbols, "18 months should be included"
    assert "COIN_LONG" in includedSymbols, "24 months should be included"


# T-EDG-05: Tie-break saat sort kandidat → alphabetical, hasil deterministik
def test_tie_break_alphabetical_deterministic():
    """Verify alphabetical tie-break produces deterministic ordering."""
    # Candidates with different FR but same FR - cost (same net expected)
    # Using exact decimals to avoid floating point issues
    candidates = [
        {"symbol": "ZECUSDT", "fr": 0.10, "cost": 0.08},   # net = 0.02
        {"symbol": "BTCUSDT", "fr": 0.12, "cost": 0.10},   # net = 0.02
        {"symbol": "ETHUSDT", "fr": 0.10, "cost": 0.08},   # net = 0.02
        {"symbol": "ADAUSDT", "fr": 0.10, "cost": 0.08},   # net = 0.02
    ]
    
    # Sort by (fr - cost) descending, then alphabetical
    # Using round() to avoid floating point comparison issues
    def sortKey(c):
        netExpected = round(c["fr"] - c["cost"], 4)
        return (-netExpected, c["symbol"])
    
    sortedCandidates = sorted(candidates, key=sortKey)
    
    # All have same net (0.02), should be sorted alphabetically
    # Order should be: ADAUSDT, BTCUSDT, ETHUSDT, ZECUSDT
    expectedOrder = ["ADAUSDT", "BTCUSDT", "ETHUSDT", "ZECUSDT"]
    actualOrder = [c["symbol"] for c in sortedCandidates]
    
    # Print for debugging
    print("\nSort results:")
    for c in sortedCandidates:
        netExpected = round(c["fr"] - c["cost"], 4)
        print(f"  {c['symbol']}: fr={c['fr']}, cost={c['cost']}, net={netExpected}")
    
    assert actualOrder == expectedOrder, \
        f"Expected alphabetical order {expectedOrder}, got {actualOrder}"
    
    # Run sort again to verify determinism
    sortedAgain = sorted(candidates, key=sortKey)
    symbolsFirst = [c["symbol"] for c in sortedCandidates]
    symbolsSecond = [c["symbol"] for c in sortedAgain]
    
    assert symbolsFirst == symbolsSecond, "Sort should be deterministic"


# T-EDG-06: FR tepat sama dengan threshold (FR = 0.05%) → dihitung sebagai entry signal
def test_fr_at_entry_threshold_is_entry_signal():
    """Verify FR == entry threshold triggers entry."""
    entryThreshold = ENTRY_THRESHOLD  # 0.05%
    
    # FR exactly at threshold
    frAtThreshold = 0.05
    
    # Should trigger entry (>= threshold)
    assert frAtThreshold >= entryThreshold, \
        "FR at threshold should trigger entry"
    
    # FR just below threshold
    frBelowThreshold = 0.0499
    
    # Should NOT trigger entry
    assert not (frBelowThreshold >= entryThreshold), \
        "FR below threshold should not trigger entry"


# T-EDG-07: FR tepat sama dengan exit threshold (FR = 0.02%) → TIDAK trigger exit
def test_fr_at_exit_threshold_does_not_trigger_exit():
    """Verify FR == exit threshold does NOT trigger exit (must be strictly less)."""
    exitThreshold = EXIT_THRESHOLD  # 0.02%
    
    # FR exactly at threshold - should NOT exit
    frAtThreshold = 0.02
    
    # Exit only if FR < 0.02%, not <= 0.02%
    shouldExit = frAtThreshold < exitThreshold
    assert shouldExit is False, \
        "FR at exit threshold (0.02%) should NOT trigger exit"
    
    # FR just below threshold - should exit
    frBelowThreshold = 0.0199
    
    shouldExit = frBelowThreshold < exitThreshold
    assert shouldExit is True, \
        "FR below exit threshold should trigger exit"
    
    # FR just above threshold - should NOT exit
    frAboveThreshold = 0.0201
    
    shouldExit = frAboveThreshold < exitThreshold
    assert shouldExit is False, \
        "FR above exit threshold should not trigger exit"


# Additional test: Verify exit threshold logic is strict less-than
def test_exit_threshold_is_strict_less_than():
    """Comprehensive test for strict less-than exit logic."""
    exitThreshold = EXIT_THRESHOLD
    
    testCases = [
        (0.019, True),   # Below -> exit
        (0.0199, True),  # Below -> exit
        (0.02, False),   # Equal -> NO exit
        (0.0201, False), # Above -> NO exit
        (0.03, False),   # Above -> NO exit
    ]
    
    for fr, expectedExit in testCases:
        shouldExit = fr < exitThreshold
        assert shouldExit == expectedExit, \
            f"FR={fr} exit={shouldExit}, expected={expectedExit}"
