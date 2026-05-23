"""
Core simulator with t+1 causality enforcement.
Implements strict temporal ordering: close -> open -> collect.
"""
import logging
import pandas as pd
from typing import Optional
from dataclasses import dataclass, field

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ENTRY_THRESHOLD, EXIT_THRESHOLD, SIZE_PER_PAIR
from engine.portfolio import Portfolio
from engine.cost_model import getCostForSymbol, getCostTierForSymbol

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """Entry or exit signal."""
    symbol: str
    signalTime: pd.Timestamp
    actionTime: pd.Timestamp
    signalType: str  # "entry" or "exit"
    triggerFr: float


@dataclass
class Simulator:
    """
    Event-driven simulator with strict t+1 causality.
    
    Core rules:
    - FR at index t can ONLY trigger action at index t+1
    - Entry and exit cannot occur at same settlement
    - Close -> Collect -> Open ordering enforced
    """
    entryThreshold: float = ENTRY_THRESHOLD
    exitThreshold: float = EXIT_THRESHOLD
    tier: str = "mid"
    portfolio: Portfolio = field(default_factory=Portfolio)
    signals: list[Signal] = field(default_factory=list)
    equityCurve: list[dict] = field(default_factory=list)
    pendingEntries: dict[str, Signal] = field(default_factory=dict)
    pendingExits: dict[str, Signal] = field(default_factory=dict)
    gapClosures: list[dict] = field(default_factory=list)
    
    def processSettlement(self, timestamp: pd.Timestamp, 
                          frData: dict[str, float]) -> None:
        """
        Process one settlement timestep.
        
        Order of operations (CRITICAL for causality):
        1. Execute pending exits from t-1 signals
        2. Execute pending entries from t-1 signals
        3. Collect FR[t] for ALL open positions (including newly opened)
        4. Generate new signals from current FR
        5. Record equity snapshot
        
        Args:
            timestamp: Current settlement timestamp
            frData: Dict mapping symbol -> FR value (%)
        """
        # Step 1: Execute pending exits (from t-1 signals)
        self._executePendingExits(timestamp, frData)
        
        # Step 2: Execute pending entries (from t-1 signals)
        self._executePendingEntries(timestamp, frData)
        
        # Step 3: Collect FR for ALL open positions (including newly opened)
        for symbol in self.portfolio.getPositionSymbols():
            if symbol in frData:
                self.portfolio.collectFr(symbol, abs(frData[symbol]))
        
        # Step 4: Generate new signals from current FR
        self._generateSignals(timestamp, frData)
        
        # Step 5: Record equity snapshot
        self.equityCurve.append(self.portfolio.getEquitySnapshot(timestamp))
    
    def _executePendingExits(self, timestamp: pd.Timestamp,
                              frData: dict[str, float]) -> None:
        """Execute exit signals from t-1."""
        symbolsToClose = list(self.pendingExits.keys())
        
        for symbol in symbolsToClose:
            signal = self.pendingExits.pop(symbol)
            
            if self.portfolio.hasPosition(symbol):
                exitFr = signal.triggerFr
                self.portfolio.closePosition(symbol, timestamp, exitFr, gapClosed=False)
                logger.debug(f"Exit executed: {symbol} at {timestamp}")
    
    def _executePendingEntries(self, timestamp: pd.Timestamp,
                                 frData: dict[str, float]) -> None:
        """Execute entry signals from t-1."""
        # Sort by expected net (FR - cost), then alphabetically
        candidates = []
        for symbol, signal in self.pendingEntries.items():
            cost = getCostForSymbol(symbol, self.tier)
            expectedNet = signal.triggerFr - cost
            candidates.append((symbol, signal, expectedNet, cost))
        
        # Sort: highest expected net first, then alphabetical
        candidates.sort(key=lambda x: (-x[2], x[0]))
        
        # Open positions
        availableSlots = self.portfolio.getAvailableSlots()
        openedSymbols = []
        
        for symbol, signal, expectedNet, cost in candidates[:availableSlots]:
            if self.portfolio.hasPosition(symbol):
                continue
            
            entryCollectFr = frData.get(symbol, 0.0)
            costTier = getCostTierForSymbol(symbol, self.tier)
            
            success = self.portfolio.openPosition(
                symbol=symbol,
                entryTime=timestamp,
                entryFr=signal.triggerFr,
                entryCollectFr=entryCollectFr,
                costRt=cost,
                costTier=costTier,
            )
            
            if success:
                openedSymbols.append(symbol)
                del self.pendingEntries[symbol]
                logger.debug(f"Entry executed: {symbol} at {timestamp}")
        
        # Clear remaining pending entries (rejected due to slot limit)
        for symbol in list(self.pendingEntries.keys()):
            if symbol not in openedSymbols:
                del self.pendingEntries[symbol]
    
    def _generateSignals(self, timestamp: pd.Timestamp,
                          frData: dict[str, float]) -> None:
        """Generate entry/exit signals for t+1."""
        for symbol, fr in frData.items():
            absFr = abs(fr)
            
            # Entry signal: |FR| >= entry threshold
            if absFr >= self.entryThreshold:
                if not self.portfolio.hasPosition(symbol):
                    signal = Signal(
                        symbol=symbol,
                        signalTime=timestamp,
                        actionTime=timestamp + pd.Timedelta(hours=8),
                        signalType="entry",
                        triggerFr=fr,
                    )
                    self.pendingEntries[symbol] = signal
                    self.signals.append(signal)
                    logger.debug(f"Entry signal: {symbol} at {timestamp}, FR={fr}%")
            
            # Exit signal: |FR| < exit threshold (strict less-than)
            if absFr < self.exitThreshold:
                if self.portfolio.hasPosition(symbol):
                    signal = Signal(
                        symbol=symbol,
                        signalTime=timestamp,
                        actionTime=timestamp + pd.Timedelta(hours=8),
                        signalType="exit",
                        triggerFr=fr,
                    )
                    self.pendingExits[symbol] = signal
                    self.signals.append(signal)
                    logger.debug(f"Exit signal: {symbol} at {timestamp}, FR={fr}%")
    
    def handleDataGap(self, gapStart: pd.Timestamp, 
                       gapEnd: pd.Timestamp) -> None:
        """
        Handle data gap by closing positions.
        
        Args:
            gapStart: Last valid timestamp before gap
            gapEnd: First valid timestamp after gap
        """
        # Close all positions at gap start
        for symbol in self.portfolio.getPositionSymbols():
            trade = self.portfolio.closePosition(
                symbol=symbol,
                exitTime=gapStart,
                exitFr=0.0,  # No FR at gap
                gapClosed=True,
            )
            if trade:
                self.gapClosures.append(trade)
                logger.info(f"Gap closure: {symbol} at {gapStart}")
        
        # Clear all pending signals
        self.pendingEntries.clear()
        self.pendingExits.clear()
    
    def getTradeLog(self) -> list[dict]:
        """Get all completed trades."""
        return self.portfolio.trades + self.gapClosures
    
    def getEquityCurve(self) -> pd.DataFrame:
        """Get equity curve as DataFrame."""
        return pd.DataFrame(self.equityCurve)


def runSimulation(frData: dict[str, pd.DataFrame], 
                   tier: str = "mid") -> Simulator:
    """
    Run full simulation on FR data.
    
    Args:
        frData: Dict mapping symbol -> DataFrame with ['timestamp', 'fr_pct']
        tier: Cost tier ("low", "mid", "high")
    
    Returns:
        Simulator with results
    """
    from engine.data_loader import buildMasterTimeline
    
    # Build master timeline
    timeline = buildMasterTimeline(frData)
    
    # Initialize simulator
    sim = Simulator(tier=tier)
    
    # Build FR lookup by timestamp
    frLookup = {}
    for symbol, df in frData.items():
        for _, row in df.iterrows():
            ts = row["timestamp"]
            if ts not in frLookup:
                frLookup[ts] = {}
            frLookup[ts][symbol] = row["fr_pct"]
    
    # Run simulation
    prevTs = None
    for ts in timeline:
        # Detect gaps
        if prevTs is not None:
            gap = ts - prevTs
            if gap > pd.Timedelta(hours=12):  # More than one missed settlement
                logger.warning(f"Gap detected: {prevTs} -> {ts}")
                sim.handleDataGap(prevTs, ts)
        
        # Get FR data for this timestamp
        tsFrData = frLookup.get(ts, {})
        
        # Process settlement
        sim.processSettlement(ts, tsFrData)
        
        prevTs = ts
    
    logger.info(f"Simulation complete: {len(sim.getTradeLog())} trades")
    
    return sim
