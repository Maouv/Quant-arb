"""
Portfolio management for slot-based position tracking.
Handles accounting, exposure limits, and P&L calculation.
"""
import logging
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MAX_PAIRS, EFFECTIVE_CAPITAL, SIZE_PER_PAIR, TOTAL_CAPITAL

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Open position for a single symbol."""
    symbol: str
    entryTime: pd.Timestamp
    entryFr: float              # FR at signal (t)
    entryCollectFr: float       # FR at first collection (t+1)
    costRt: float
    costTier: str = "tier"
    grossCollected: float = 0.0
    holdSettlements: int = 0
    gapClosed: bool = False
    
    def collectFr(self, frValue: float) -> None:
        """Add FR to gross collected."""
        self.grossCollected += abs(frValue)
        self.holdSettlements += 1
    
    def close(self, exitTime: pd.Timestamp, exitFr: float, 
              gapClosed: bool = False) -> dict:
        """
        Close position and return trade record.
        
        Args:
            exitTime: Timestamp of exit
            exitFr: FR at exit signal
            gapClosed: Whether closed due to data gap
        
        Returns:
            Trade dict with P&L
        """
        netPct = self.grossCollected - self.costRt
        grossDollar = self.grossCollected / 100 * SIZE_PER_PAIR
        costDollar = self.costRt / 100 * SIZE_PER_PAIR
        netDollar = netPct / 100 * SIZE_PER_PAIR
        
        return {
            "trade_id": f"{self.symbol}_{self.entryTime.strftime('%Y%m%d%H%M%S')}",
            "symbol": self.symbol,
            "side": "long_spot_short_futures",
            "entry_time": self.entryTime,
            "exit_time": exitTime,
            "entry_fr": self.entryFr,
            "entry_collect_fr": self.entryCollectFr,
            "exit_fr": exitFr,
            "hold_settlements": self.holdSettlements,
            "gross_pct": self.grossCollected,
            "cost_rt_pct": self.costRt,
            "net_pct": netPct,
            "gross_dollar": grossDollar,
            "cost_dollar": costDollar,
            "net_dollar": netDollar,
            "cost_tier": self.costTier,
            "gap_closed": gapClosed,
        }


@dataclass
class Portfolio:
    """Portfolio with slot-based position management."""
    maxPairs: int = MAX_PAIRS
    effectiveCapital: float = EFFECTIVE_CAPITAL
    sizePerPair: float = SIZE_PER_PAIR
    positions: dict[str, Position] = field(default_factory=dict)
    trades: list[dict] = field(default_factory=list)
    balance: float = field(default_factory=lambda: TOTAL_CAPITAL)
    peakEquity: float = field(default_factory=lambda: TOTAL_CAPITAL)
    
    def canOpenPosition(self) -> bool:
        """Check if slot available."""
        return len(self.positions) < self.maxPairs
    
    def getAvailableSlots(self) -> int:
        """Get number of available slots."""
        return self.maxPairs - len(self.positions)
    
    def openPosition(self, symbol: str, entryTime: pd.Timestamp,
                     entryFr: float, entryCollectFr: float,
                     costRt: float, costTier: str) -> bool:
        """
        Open a new position.
        
        Args:
            symbol: Trading pair
            entryTime: Entry timestamp
            entryFr: FR at signal (t)
            entryCollectFr: FR at first collection (t+1) - NOT used, kept for API compat
            costRt: Round-trip cost %
            costTier: Cost tier label
        
        Returns:
            True if opened, False if no slot
        
        Note: First FR collection happens in Step 3 (collect phase), not here.
        """
        if not self.canOpenPosition():
            logger.debug(f"No slot available for {symbol}")
            return False
        
        if symbol in self.positions:
            logger.warning(f"Position already exists for {symbol}")
            return False
        
        pos = Position(
            symbol=symbol,
            entryTime=entryTime,
            entryFr=entryFr,
            entryCollectFr=entryCollectFr,
            costRt=costRt,
            costTier=costTier,
        )
        # Note: First FR is collected in Step 3 (collect phase), not here
        
        self.positions[symbol] = pos
        logger.debug(f"Opened position: {symbol} at {entryTime}, FR={entryFr}%")
        return True
    
    def collectFr(self, symbol: str, frValue: float) -> None:
        """
        Collect FR for an open position.
        
        Args:
            symbol: Trading pair
            frValue: FR value to collect (%)
        """
        if symbol not in self.positions:
            logger.warning(f"No position for {symbol}")
            return
        
        self.positions[symbol].collectFr(frValue)
    
    def closePosition(self, symbol: str, exitTime: pd.Timestamp,
                      exitFr: float, gapClosed: bool = False) -> Optional[dict]:
        """
        Close a position.
        
        Args:
            symbol: Trading pair
            exitTime: Exit timestamp
            exitFr: FR at exit signal
            gapClosed: Whether closed due to gap
        
        Returns:
            Trade dict or None if no position
        """
        if symbol not in self.positions:
            logger.warning(f"No position to close for {symbol}")
            return None
        
        pos = self.positions[symbol]
        trade = pos.close(exitTime, exitFr, gapClosed)
        
        del self.positions[symbol]
        self.trades.append(trade)
        self.balance += trade["net_dollar"]
        
        logger.debug(f"Closed position: {symbol}, net={trade['net_pct']:.4f}%")
        return trade
    
    @property
    def exposure(self) -> float:
        """Total capital deployed."""
        return len(self.positions) * self.sizePerPair
    
    @property
    def unrealizedPnl(self) -> float:
        """Sum of unrealized gross from open positions."""
        return sum(pos.grossCollected / 100 * self.sizePerPair 
                   for pos in self.positions.values())
    
    @property
    def equity(self) -> float:
        """Total equity (balance + unrealized)."""
        return self.balance + self.unrealizedPnl
    
    @property
    def openPositionsCount(self) -> int:
        """Count of open positions."""
        return len(self.positions)
    
    def getEquitySnapshot(self, timestamp: pd.Timestamp) -> dict:
        """
        Get equity snapshot for a timestamp.
        
        Args:
            timestamp: Current timestamp
        
        Returns:
            Dict with equity metrics
        """
        equity = self.equity
        self.peakEquity = max(self.peakEquity, equity)
        drawdownDollar = equity - self.peakEquity
        drawdownPct = (drawdownDollar / self.peakEquity * 100) if self.peakEquity > 0 else 0.0
        
        return {
            "timestamp": timestamp,
            "balance": self.balance,
            "unrealized_pnl": self.unrealizedPnl,
            "equity": equity,
            "drawdown_dollar": drawdownDollar,
            "drawdown_pct": drawdownPct,
            "open_positions": self.openPositionsCount,
            "exposure": self.exposure,
        }
    
    def hasPosition(self, symbol: str) -> bool:
        """Check if position exists for symbol."""
        return symbol in self.positions
    
    def getPositionSymbols(self) -> list[str]:
        """Get list of symbols with open positions."""
        return list(self.positions.keys())
