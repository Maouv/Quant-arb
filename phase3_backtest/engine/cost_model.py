"""
Cost model for assigning round-trip cost per symbol.
Uses actual costs from Phase 0 sampling where available,
falls back to tier-based costs otherwise.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ACTUAL_COSTS, COST_TIERS


def getCostForSymbol(symbol: str, tier: str = "mid") -> float:
    """
    Return round-trip cost % for symbol.
    
    If symbol has actual Phase 0 cost -> use it.
    Otherwise -> use tier (low/mid/high).
    
    Args:
        symbol: Trading pair symbol (e.g., "ETHUSDT")
        tier: Cost tier to use ("low", "mid", "high")
    
    Returns:
        Round-trip cost as percentage
    
    Raises:
        ValueError: If tier is invalid
    """
    # Check for actual cost first
    if symbol in ACTUAL_COSTS:
        return ACTUAL_COSTS[symbol]
    
    # Fall back to tier
    if tier not in COST_TIERS:
        raise ValueError(f"Invalid tier '{tier}'. Must be one of: {list(COST_TIERS.keys())}")
    
    return COST_TIERS[tier]


def getCostTierForSymbol(symbol: str, tier: str) -> str:
    """
    Return the cost tier label for a symbol.
    
    Args:
        symbol: Trading pair symbol
        tier: Tier parameter ("low", "mid", "high")
    
    Returns:
        "actual" if symbol has Phase 0 cost, else tier
    """
    if symbol in ACTUAL_COSTS:
        return "actual"
    return tier


def summarizeCostDistribution(symbols: list[str], tier: str) -> dict:
    """
    Summarize cost distribution for a set of symbols.
    
    Args:
        symbols: List of trading pair symbols
        tier: Tier to use for non-actual costs
    
    Returns:
        Dict with cost statistics
    """
    costs = [getCostForSymbol(s, tier) for s in symbols]
    
    actualSymbols = [s for s in symbols if s in ACTUAL_COSTS]
    tierSymbols = [s for s in symbols if s not in ACTUAL_COSTS]
    
    return {
        "total_symbols": len(symbols),
        "actual_cost_symbols": len(actualSymbols),
        "tier_cost_symbols": len(tierSymbols),
        "min_cost": min(costs),
        "max_cost": max(costs),
        "avg_cost": sum(costs) / len(costs),
        "actual_cost_list": actualSymbols,
    }
