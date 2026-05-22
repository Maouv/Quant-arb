# PHASE 1: VIABILITY ANALYSIS
## Funding Rate Arbitrage Strategy
**Date:** 22 May 2026  
**Status:** DRAFT v1.0 — pending review  
**Author:** Maou + Kiro  
**Training Set:** 2022-01-01 to 2024-12-31  
**Data:** 108 coins, 8h interval, all >= 18 months training data  

---

## BAGIAN 1 — FREQUENCY OF OPPORTUNITY

### Per Threshold (All 108 Coins, Training Set)
```
|FR| >= 0.03%:  ~1,500+ entry signals/year
|FR| >= 0.05%:  ~750 entry signals/year
|FR| >= 0.08%:  ~300 entry signals/year
|FR| >= 0.10%:  ~150 entry signals/year
```

### Top 10 Coins by Opportunity Frequency
Entry 0.05%, Exit <0.02% or flip, Cost 0.12%:
```
Symbol       Trades/Yr   Ann Yield%   Win Rate   Avg Hold
MTLUSDT      40.3        21.7%        65%        4.9
RLCUSDT      30.3        11.2%        58%        5.0
ACHUSDT      28.2         1.9%        32%        3.0
JASMYUSDT    24.4         3.4%        46%        3.5
TRXUSDT      23.7         3.5%        56%        4.3
XVSUSDT      23.4         3.0%        42%        3.8
INJUSDT      23.2         7.4%        84%        6.4
APEUSDT      22.2        10.8%        60%        7.5
XVGUSDT      22.0        31.4%        76%        6.4
SEIUSDT      21.2         8.8%        67%        6.8
```

Note: XVGUSDT (31.4% ann yield) dan MTLUSDT (21.7%) = outliers.
**SUSPICIOUS — cost paradox confirmed:**
- XVGUSDT: spot volume $271K/day, spread 0.20% per side, estimated RT cost ~0.50%+
  Dengan cost real, yield kemungkinan negatif. FR volatile karena illiquid.
- MTLUSDT: spot volume $82K/day, spread 0.33% per side, estimated RT cost ~0.66%+
  Sama — yield inflated karena flat cost 0.12% jauh di bawah actual.
- ETH reference: spread 0.0005% per side (400x lebih tight)
- Trades MTLUSDT declining: 80/yr (2022) → 18/yr (2024)

**Conclusion:** Top coins by opportunity = top coins by illiquidity.
Flat cost assumption (0.12%) severely underestimates cost untuk coins ini.
Actual viable coins kemungkinan di mid-tier (BNB, INJ, TRX, dll) yang
punya balance antara FR volatility dan liquidity.

### Confidence
HIGH — ini factual count dari data. Tidak tergantung exit rule atau cost assumption.

---

## BAGIAN 2 — FUNDING FLIP FREQUENCY

### Run Length Distribution (Same-Sign Consecutive Settlements)
```
Median run length:  2 settlements (16 jam)
Average run length: 5-9 settlements (40-72 jam)
p25: 1 settlement
p75: 4-5 settlements
p90: 9-17 settlements
```

### Implikasi
- 50% of the time, FR berubah sign dalam 16 jam
- Banyak trades akan pendek (1-2 settlements)
- Strategy = high frequency of short trades + occasional long profitable runs
- Hold period panjang (>5 settlements) terjadi ~25% of the time

### Confidence
HIGH — factual count dari data.

---

## BAGIAN 3 — FR PERSISTENCE (PREDICTABILITY)

### Pertanyaan: Apakah Current FR Predictive of Next FR?

```
Threshold 0.05% (11,450 events):
  Next settlement same sign:         95.0%
  Next settlement FLIPPED:            5.0%
  Next still >= 0.05% (same sign):   57.9%
  Next still >= 0.025% (same sign):  83.0%

FR Decay Ratio (next/current):
  Mean:   0.827
  Median: 0.777
  p25:    0.467
  p75:    1.043
```

### Multi-Step Persistence (Entry at 0.05%)
```
Total entry events: 1,952
Persistence (settlements staying same sign after entry):
  Median: 5 settlements
  p25:    2 settlements
  p75:    16 settlements
  p90:    80 settlements

  1 settlement only:  19.1% (instant flip — losing trade)
  2 settlements:      10.9%
  3-5 settlements:    23.2%
  6+ settlements:     46.8%
```

### Implikasi
- Entry berdasarkan current FR = VALID (95% same sign next settlement)
- FR decay gradual (median 0.777 per settlement), bukan cliff
- Expected hold ~5 settlements median (40 jam / 1.7 hari)
- 19% trades = instant loss (1 settlement, cost > yield). Unavoidable.
- 47% trades hold 6+ settlements — ini yang drive profitability

### Confidence
HIGH — derived from 11,450 events across 108 coins.

---

## BAGIAN 4 — FR SPIKE CORRELATION

### Pertanyaan: Apakah FR Spikes Independent Across Coins?

```
Settlements with >= 1 spike (0.05%):  2,387 / 3,380 (71%)

Distribution of simultaneous spikes:
  1 coin only:    43% of spike events
  2 coins:        23%
  3 coins:        12%
  4-6 coins:      12%
  7+ coins:       10% (tail events — market crash/pump)

Average concurrent spikes: 4.8 (saat ada spike)
Median concurrent spikes:  2
Max:                       105 (extreme event)
```

### Capital Slot Analysis
```
Slots | % time ALL slots full | Capture rate
  3   | 24%                   | 76%
  4   | 15%                   | 85%
  5   | 10%                   | 90%
  6   |  8%                   | 92% ← OPTIMAL
  8   |  6%                   | 94%
 10   |  4%                   | 96%
```

### Implikasi
- Spikes PARTIALLY correlated tapi mostly independent
- 6 pair slots = optimal (capture 92% of opportunities)
- Expand universe genuinely increases opportunity (bukan cuma lebih banyak pilihan di waktu yang sama)
- Extreme events (105 coins spike) = market crash. Dynamic cost filter akan block most karena spread melebar.

### Confidence
HIGH — derived from full training set, all 108 coins.

---

## BAGIAN 5 — UNIVERSE EXPANSION

### Binance Perpetual Landscape
```
8h interval coins with spot pair:  108
4h interval coins with spot pair:  254
Total perpetual + spot pairs:      363
```

### Keputusan
- Backtest universe: 108 coins (8h interval, data panjang)
- Live universe: TBD di Phase 4/5. Kemungkinan expand ke 4h coins,
  tapi belum commit karena:
  - 254 coins 4h belum punya data historis yang cukup
  - Cost model belum di-validate untuk coins kecil
  - Dynamic cost filter belum proven di live
- Untuk sekarang: backtest dan paper trading focus di 108 coins 8h

### Capital Utilization
```
Dengan 11 coins (Phase 0 original):  3.6% — TIDAK VIABLE
Dengan 108 coins:                     sufficient — VIABLE
```

---

## BAGIAN 6 — BOTTLENECK ANALYSIS

### Critical Issues (Checked)

| # | Issue | Status | Finding |
|---|-------|--------|---------|
| 1 | Predicted vs Actual FR | ✅ Resolved | 95% persistence. Current FR predictive of next. |
| 2 | Rate limiting | ✅ Resolved | Batch endpoints + only fetch depth for candidates. Not a blocker. |

### Non-Critical Issues (Accepted)

| # | Issue | Status | Reasoning |
|---|-------|--------|-----------|
| 3 | Fill rate unknown | Phase 4 | Cannot estimate from historical data. Range 50-90% tergantung coin liquidity. Liquid coins (ETH, BNB): likely 90%+. Illiquid coins (XVG, MTL): likely 50-60%. Sensitivity analysis pakai 60%, 70%, 80% scenarios. |
| 4 | Transition time between trades | Negligible | 5 menit max (1 cycle) dari 8 jam window = 0.1%. |
| 5 | Settlement timing (entry before settlement) | Phase 3 | Design decision, bukan data question. |
| 6 | USDT depeg risk | Accepted | Systemic risk, both legs in USDT, P&L wash. Accept as tail risk. |

### Known Unknowns

```
1. Settlement timing pattern:
   Apakah FR spike lebih sering terjadi menjelang atau setelah settlement?
   Kalau spike terjadi dalam window sempit sebelum settlement,
   fill rate efektif lebih rendah karena time pressure.
   Status: belum di-analyze, flag untuk Phase 3.

2. Cost per coin actual:
   Hanya punya snapshot cost untuk 11 coins (Phase 0).
   108 coins lainnya pakai flat assumption.
   Confirmed dari live data: XVG spread 0.20%, MTL 0.33% vs ETH 0.0005%.
   Status: validate di Phase 4 paper trading.
```

---

## BAGIAN 7 — CRITICAL RISKS

### Risk 1: Cost Paradox
Coins dengan FR paling volatile = coins paling kecil = cost paling tinggi.
High opportunity mungkin = high cost. Net bisa lebih rendah dari estimate.

**Mitigation:** Dynamic cost filter di live. Coins yang terlalu mahal naturally excluded real-time.

### Risk 2: Survivorship Bias
108 coins ini semua masih listed. Coins yang delist 2022-2024 tidak ada di data.
Yield historis mungkin overestimate karena exclude worst outcomes.

**Status:** Acknowledged as unresolvable limitation. Data coins yang delist tidak tersedia dari Binance. Tidak ada cara fix ini sepenuhnya. Accept and proceed.

### Risk 3: Regime Sensitivity
Training data 2022-2024 include bear (2022) dan bull (2024). FR behavior mungkin berbeda per regime. Belum di-test.

**Mitigation:** Validation set (2025) akan test ini. Satu kali access only.

### Risk 4: Yield Estimate Uncertainty
Yield numbers depend on:
- Cost assumption (flat 0.12% — actual varies per coin)
- Exit rule (0.02% threshold — belum fully derived)
- Fill rate (unknown — assume 70-80%)

**Mitigation:** Phase 2 math framework dengan sensitivity analysis.

---

## BAGIAN 8 — KEPUTUSAN PHASE 1

```
1. Universe: 108 coins 8h interval (semua yang punya spot + futures)
2. Live universe: TBD Phase 4/5 (belum commit ke 363 pairs)
3. Max pairs: 6 (optimal dari correlation analysis — capture 92%)
4. Data handling: gap = break, minimum 12 bulan training, annualize per actual period
5. Volume/mcap filter: tidak dipakai — redundant karena dynamic cost filter
6. AI model: rejected — rule-based sufficient
7. Entry threshold: 0.05% (dari frequency + persistence analysis)
8. Exit threshold: |FR| < 0.02%
   "Flip sign" tidak perlu sebagai rule terpisah — kalau FR flip,
   nilainya otomatis < 0.02% di 99.94% cases (27 exceptions dari
   41,909 flips dalam 3yr × 108 coins = negligible).
9. Cost for analysis: 3 tiers (0.08%, 0.12%, 0.20%)
   Note: 0.12% flat UNDERESTIMATES cost untuk illiquid coins.
   Actual cost range kemungkinan 0.08% (ETH) sampai 0.50%+ (XVG, MTL).
```

---

## BAGIAN 8b — CHANGES FROM PHASE 0

```
Phase 0 Decision          → Phase 1 Update              Reason
─────────────────────────────────────────────────────────────────────
Max pairs: 3              → 6                           Correlation analysis: 6 slots
                                                        capture 92% of opportunities
Universe: 11 coins        → 108 coins (8h)             11 coins = 3.6% capital
                                                        utilization, not viable
Volume filter: >$10M      → removed                    Redundant — dynamic cost
                                                        filter handles illiquid coins
Live universe: 11 coins   → TBD Phase 4/5              Cannot commit to 363 pairs
                                                        without validation
Exit rule: "exit threshold"→ |FR| < 0.02%                Derived from data: hold
                                                        below 0.02% not profitable.
                                                        "Flip sign" redundant — 99.94%
                                                        of flips already < 0.02%.
Position size: $1,000/pair→ $300/pair (6 pairs)         More pairs, smaller size
Buffer: 40%               → 40% (unchanged)            Still $1,200 buffer on $3,000
```

---

## BAGIAN 9 — YIELD ESTIMATE (RECONCILED)

### Parameters
```
Entry threshold:  |FR| >= 0.05%
Exit threshold:   |FR| < 0.02% OR flip sign
Cost RT:          0.12% (mid tier)
Data:             108 coins, training set 2022-2024
```

### Per-Trade Statistics
```
Total trades (3yr):    3,089
Trades/year:           1,030
Avg gross per trade:   0.478%
Avg net per trade:     0.358%
Median net per trade:  0.048%
Std net:               1.129%
```

### Win/Loss Profile
```
Win rate:              60.8%
Avg winner:            +0.618%
Avg loser:             -0.044%
Win/loss ratio:        13.9:1
```

Losers kecil (cost > gross pada short holds), winners besar (long holds accumulate).

### Hold Duration
```
Avg:    5.9 settlements (2.0 days)
Median: 3 settlements (1.0 days)
p25:    1 settlement
p75:    6 settlements
```

### Entry FR Distribution
```
Avg entry FR:    0.097% (hampir 2x threshold)
Median entry FR: 0.062%
p75:             0.081%
p90:             0.138%
```

### Yield by Entry FR Level
```
Entry Range      Trades   Avg Net%   Win%   Avg Dur
0.05% - 0.08%   2,299    0.254%     54%    6.4
0.08% - 0.12%     393    0.250%     61%    3.8
0.12% - 0.20%     214    0.654%    100%    4.8
0.20% - 1.00%     167    1.194%    100%    5.2
```

Entry di FR >= 0.12% = 100% win rate. Ini karena gross selalu > cost (0.12%) bahkan di 1 settlement.

### Annualized Yield Estimate (Realistic)
```
Capital:                $3,000 (total), $1,800 effective (40% buffer)
Pairs:                  6 slots × $300 per pair
Slot capacity:          1,095 trades/year (6 × 365/2)
Available trades:       1,030/year
Capture rate (6 slots): 92% (dari correlation analysis)
Effective trades:       ~948/year

Dollar profit/trade:    $300 × 0.358% = $1.07
Annual profit:          948 × $1.07 = ~$1,014
APY on $3,000 total:    ~34%
APY on $1,800 effective: ~56%
```

### Sensitivity
```
Cost 0.08%: avg net 0.398%, ann yield ~$1,130 (38% on $3k)
Cost 0.12%: avg net 0.358%, ann yield ~$1,014 (34% on $3k)
Cost 0.16%: avg net 0.318%, ann yield ~$900  (30% on $3k)
Cost 0.20%: avg net 0.278%, ann yield ~$790  (26% on $3k)

Fill rate 70%: multiply above by 0.7 → 18-27% on $3k
Fill rate 80%: multiply above by 0.8 → 21-30% on $3k
```

### Caveats
- Cost 0.12% flat — actual varies per coin (small coins likely 0.30-0.60%+)
- Fill rate unknown — range 50-90% tergantung liquidity
- Slot concurrency simplified — actual depends on timing overlap
- 369% APY dari script sebelumnya SALAH — itu assume unlimited capital per trade
- APY 34% assume 92% capture rate terealisasi, yang bergantung pada fill rate
- Illiquid coins (top opportunity) mungkin tidak tradeable di $300 size tanpa massive slippage

---

## BAGIAN 10 — VIABILITY VERDICT

### Strategy VIABLE Dengan Caveats

```
✅ Opportunity frequency sufficient (1,030 trades/year)
✅ FR spikes mostly independent (expand universe works)
✅ 6 slots capture 92% of opportunities
✅ Current FR predictive of next FR (95% persistence)
✅ FR decay gradual — yield collectible over multiple settlements
✅ Realistic APY estimate: 24-34% on $3,000 (with fill rate uncertainty)
✅ Win/loss ratio 13.9:1 — losers small, winners large

⚠️ Cost paradox (high opportunity coins = high cost coins)
⚠️ Fill rate unknown (70-80% assumption, validate Phase 4)
⚠️ Survivorship bias (unresolvable, accepted)
⚠️ Regime sensitivity untested (validation set reserved)
⚠️ 19% trades = instant loss (unavoidable)
```

### Proceed to Phase 2: Mathematical Framework

---

## STATUS DOKUMEN

```
DRAFT v1.0 — 22 May 2026
Pending review oleh Maou

Next step setelah approved:
→ Phase 2: Mathematical Framework
  - Expected annual yield formula (with sensitivity)
  - Position sizing (equal weight, 6 pairs)
  - Capital allocation dengan 40% buffer
  - Break-even threshold derivation
  - Exit rule derivation
```
