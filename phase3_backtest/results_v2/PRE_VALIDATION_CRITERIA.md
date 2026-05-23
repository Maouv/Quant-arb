# Pre-committed Validation Criteria — 2025 OOS Test
Date committed: 2026-05-23
Status: LOCKED — tidak boleh diubah setelah 2025 data dibuka

## Baseline (training set, mid-tier, 2022–2024)
- Net mid-tier 3yr: $833.56 (1720 trades)
- Annualized: $277.85/yr
- Win rate: 34.1%
- Avg hold: 3.9 settlements

## Rejection criteria (ANY one → reject)
- Net 2025 < $278 (annualized dari $833.56 baseline / 3 tahun)
- Max drawdown 2025 > $50
- Win rate 2025 < 25%
- Top 10% trades > 85% of total net

## Acceptance criteria (ALL must pass)
- Net 2025 >= $278
- Max drawdown <= $50
- Win rate >= 30%
- Top 10% trades <= 70% of total net

## Statistical battery results (training set)
- B1 Trade Bootstrap CI 95%: [$644, $1038] — prob_negative=0.000 — PASS
- B2 Block Bootstrap CI 95%: [$576, $1139] — lower > 0 — PASS
- B3 Sign Randomization: p=0.000 — PASS
- B4 Cost gradient break-even: 0.26% — PASS

## Notes
- Universe: 97 symbols (100 minus 3 non-8h interval coins)
- NEARUSDT excluded by rule (structural cost > yield)
- 7 coins excluded by <18 months training data: AGLDUSDT, ARKMUSDT, BICOUSDT, BNTUSDT, PENDLEUSDT, SEIUSDT, WLDUSDT
- Cost tier mid = 0.12% for 90 coins; 10 coins use actual Phase 0 costs
- Execution assumption: 100% fill rate, no slippage beyond cost model
- 2025 data to be opened ONCE, after adversarial audit completes
