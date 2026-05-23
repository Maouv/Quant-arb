# PHASE 3: REQUIREMENTS FROM PHASE 2 REVIEW
**Date:** 22 May 2026
**Source:** Phase 2 critical review

---

## DATA
Backtest hanya butuh: **funding rate per coin per 8h** (data yang sama dengan Phase 1).
OHLCV tidak diperlukan — strategi delta-neutral, price movement net ≈ 0.
Cost disimulasi dari flat tier (Phase 0), bukan dari live orderbook.

---

## MUST-VALIDATE (dari conceptual weaknesses Phase 2)

### 1. Drawdown Analysis
- Max consecutive losing trades
- Max drawdown (dollar dan %)
- Max drawdown duration (days)
- Reason: Annual Sharpe ~10 implies trades NOT iid. Average yield meaningless tanpa drawdown context.

### 2. Per-Regime Performance
- Segment backtest: bull / bear / sideways
- Check apakah T (trades/year) stabil across regimes atau drop 30-50% di certain periods
- If T drops significantly → absolute floor 13.2% terlalu optimistis

### 3. Decay Model Validation
- Compare predicted gross (d=0.777 geometric model) vs actual gross per trade
- Current gap: model predicts 0.337%, actual 0.478%
- Identify source of discrepancy (right-skew entries? long-tail holds?)

### 4. Stress-Test Frequency Parameter T
- What is T in worst 6-month window?
- If T_worst < 700/year → recalculate absolute floor
- True worst-case floor might be ~9% (not 13.2%)

### 5. Derive min_profit_threshold
- Phase 2 leaves `buffer_margin` undefined
- Backtest should determine: minimum net_expected per trade that still contributes positively after accounting for variance
- Candidate: 0.01% buffer above break-even

### 6. Median Hold Structural Fragility ⚠️
- FR_min(n=3, cost 0.12%) = 0.050% = tepat sama dengan entry threshold
- Median hold = 3 settlements → 50% trades persis di break-even
- Validate: apakah trades dengan hold ≤ 3 settlements aggregate net positive atau negative?
- Jika net negative → entry threshold harus dinaikkan atau min_profit_threshold harus > 0

---

## EXISTING SCOPE (dari phase2.md STATUS)

- Code struktur production
- Simulate entry/exit dengan dynamic cost model
- Stress test: LUNA crash, FTX collapse, BTC Aug 2024
- Validate actual yield vs formula Phase 2

---

## FROM PHASE 0/1 FLAGS

- Settlement timing pattern analysis (Phase 1 Bagian 6)
- Synthetic survivorship stress test (decisions-phase0.md)
- VPS API connectivity test (phase0-api-docs.md)
