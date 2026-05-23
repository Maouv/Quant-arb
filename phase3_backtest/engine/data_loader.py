"""
Data loader for funding rate CSV files.
Handles loading, validation, and gap detection.
"""
import os
import logging
import pandas as pd
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DATA_PATH, TRAINING_START, TRAINING_END, MIN_TRAINING_MONTHS, EXCLUDED_SYMBOLS

logger = logging.getLogger(__name__)


def loadDataPath(basePath: str = DATA_PATH) -> list[str]:
    """
    Find all valid FR CSV files in data directory.
    
    Args:
        basePath: Path to funding rate data directory
    
    Returns:
        List of valid CSV file paths
    """
    files = []
    skipPatterns = ["_phase1_results.csv", "_summary.csv"]
    
    if not os.path.exists(basePath):
        raise FileNotFoundError(f"Data path not found: {basePath}")
    
    for f in os.listdir(basePath):
        if not f.endswith(".csv"):
            continue
        if any(skip in f for skip in skipPatterns):
            logger.debug(f"Skipping non-FR file: {f}")
            continue
        files.append(os.path.join(basePath, f))
    
    logger.info(f"Found {len(files)} potential FR data files")
    return files


def loadFundingRateData(filePath: str) -> Optional[pd.DataFrame]:
    """
    Load and validate a single FR CSV file.
    
    Args:
        filePath: Path to CSV file
    
    Returns:
        DataFrame with validated FR data, or None if invalid
    """
    try:
        df = pd.read_csv(filePath)
    except Exception as e:
        logger.error(f"Failed to read {filePath}: {e}")
        return None
    
    # Check required columns
    requiredCols = ["calc_time", "funding_interval_hours", "last_funding_rate"]
    missingCols = [c for c in requiredCols if c not in df.columns]
    if missingCols:
        logger.error(f"Missing columns in {filePath}: {missingCols}")
        return None
    
    # Convert timestamp to datetime
    df["timestamp"] = pd.to_datetime(df["calc_time"], unit="ms", utc=True)
    
    # Validate funding interval
    if not (df["funding_interval_hours"] == 8).all():
        logger.error(f"Non-8h intervals in {filePath}")
        return None
    
    # Convert FR to percentage (multiply by 100)
    df["fr_pct"] = df["last_funding_rate"] * 100
    
    # Sort by timestamp
    df = df.sort_values("timestamp").reset_index(drop=True)
    
    return df[["timestamp", "fr_pct"]]


def validateDataDuration(df: pd.DataFrame, symbol: str) -> bool:
    """
    Check if data covers minimum training period.
    
    Args:
        df: DataFrame with timestamp column
        symbol: Symbol name for logging
    
    Returns:
        True if data duration >= MIN_TRAINING_MONTHS
    """
    if df.empty:
        logger.warning(f"No data for {symbol}")
        return False
    
    minDate = df["timestamp"].min()
    maxDate = df["timestamp"].max()
    
    durationMonths = (maxDate.year - minDate.year) * 12 + (maxDate.month - minDate.month)
    
    if durationMonths < MIN_TRAINING_MONTHS:
        logger.warning(f"{symbol}: {durationMonths} months < {MIN_TRAINING_MONTHS} required, skipping")
        return False
    
    return True


def filterTrainingPeriod(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter data to training period only (2022-01-01 to 2024-12-31).
    
    Args:
        df: DataFrame with timestamp column
    
    Returns:
        Filtered DataFrame
    """
    startDate = pd.Timestamp(TRAINING_START, tz="UTC")
    endDate = pd.Timestamp(TRAINING_END, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    
    mask = (df["timestamp"] >= startDate) & (df["timestamp"] <= endDate)
    return df[mask].copy()


def detectGaps(df: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """
    Detect gaps in 8h settlement sequence.
    
    Args:
        df: DataFrame with timestamp column, sorted
    
    Returns:
        List of (gap_start, gap_end) tuples
    """
    gaps = []
    expectedInterval = pd.Timedelta(hours=8)
    
    for i in range(1, len(df)):
        actualInterval = df.iloc[i]["timestamp"] - df.iloc[i-1]["timestamp"]
        
        if actualInterval > expectedInterval * 1.5:  # Allow some tolerance
            gaps.append((df.iloc[i-1]["timestamp"], df.iloc[i]["timestamp"]))
            logger.debug(f"Gap detected: {df.iloc[i-1]['timestamp']} -> {df.iloc[i]['timestamp']}")
    
    return gaps


def loadAllFundingRates(basePath: str = DATA_PATH) -> dict[str, pd.DataFrame]:
    """
    Load all valid FR data files.
    
    Args:
        basePath: Path to funding rate data directory
    
    Returns:
        Dict mapping symbol -> DataFrame
    """
    files = loadDataPath(basePath)
    data = {}
    skipped = []
    
    for filePath in files:
        # Extract symbol from filename
        filename = os.path.basename(filePath)
        symbol = filename.replace("-fundingRate.csv", "")
        
        # Check exclusion list
        if symbol in EXCLUDED_SYMBOLS:
            logger.info(f"Skipping excluded symbol: {symbol}")
            skipped.append(symbol)
            continue
        
        # Load data
        df = loadFundingRateData(filePath)
        if df is None:
            continue
        
        # Validate duration
        if not validateDataDuration(df, symbol):
            skipped.append(symbol)
            continue
        
        # Filter to training period
        df = filterTrainingPeriod(df)
        
        if df.empty:
            logger.warning(f"No training data for {symbol}")
            skipped.append(symbol)
            continue
        
        # Detect and log gaps
        gaps = detectGaps(df)
        if gaps:
            logger.info(f"{symbol}: {len(gaps)} gaps detected")
        
        data[symbol] = df.reset_index(drop=True)
    
    logger.info(f"Loaded {len(data)} symbols, skipped {len(skipped)}")
    logger.info(f"Skipped symbols: {skipped}")
    
    return data


def buildMasterTimeline(data: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    """
    Build master timeline of all settlement timestamps.
    
    Args:
        data: Dict of symbol -> DataFrame
    
    Returns:
        Sorted DatetimeIndex of unique settlement timestamps
    """
    allTimestamps = set()
    
    for df in data.values():
        allTimestamps.update(df["timestamp"].tolist())
    
    timeline = pd.DatetimeIndex(sorted(allTimestamps))
    logger.info(f"Master timeline: {len(timeline)} settlements from {timeline.min()} to {timeline.max()}")
    
    return timeline
