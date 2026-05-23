# PHASE 2: MATHEMATICAL FRAMEWORK
## Funding Rate Arbitrage Strategy
**Date:** 22 May 2026
**Status:** DRAFT v1.0
**Author:** Maou + Kiro
**Depends on:** phase0.md (cost model, governance), phase1.md (viability analysis)

---

## BAGIAN 1 — EXPECTED ANNUAL YIELD FORMULA

### Variable Definitions

```
C        = total capital                   = $3,000
b        = buffer ratio                    = 0.40
C_eff    = effective capital               = C × (1 - b) = $1,800
S        = max slots (pairs simultaneous)  = 6
size     = size per pair                   = C_eff / S = $300
             → $150 spot + $150 futures margin

T        = theoretical trades/year         = 1,030  (dari Phase 1)
κ        = capture rate                    = 0.92   (6 slots, dari Phase 1 correlation analysis)
φ        = fill rate                       = unknown, range [0.50, 0.90]
FR_avg   = average gross FR per trade      = fungsi dari entry threshold
cost_rt  = round-trip cost per trade       = fee + spread + slippage (per coin)
net_avg  = average net per trade           = FR_avg - cost_rt
```

### Formula

**Net profit per trade (dalam dollar):**
```
P_trade = size × net_avg
        = (C_eff / S) × (FR_avg - cost_rt)
```

**Total annual profit:**
```
P_annual = T × κ × φ × P_trade
         = T × κ × φ × (C_eff / S) × (FR_avg - cost_rt)
```

**APY on total capital:**
```
APY = P_annual / C
    = T × κ × φ × [(1 - b) / S] × (FR_avg - cost_rt)
```

Ini adalah formula canonical Phase 2. Semua parameter kecuali φ sudah diketahui dari Phase 0–1.

### Instansiasi dengan Angka Phase 1

Entry 0.05%, exit 0.02%, cost 0.12%:
```
net_avg  = 0.358%   (dari Phase 1, avg net per trade)
P_trade  = $300 × 0.00358 = $1.074 per trade

P_annual = 1,030 × 0.92 × φ × $1.074
         = 948 × φ × $1.074
         = $1,018 × φ

APY = ($1,018 × φ) / $3,000 = 33.9% × φ
```

### Sensitivity terhadap Fill Rate φ

| Fill Rate φ | P_annual | APY on $3,000 |
|-------------|----------|---------------|
| 90%         | $916     | 30.5%         |
| 80%         | $814     | 27.2%         |
| 70%         | $713     | 23.8%         |
| 60%         | $611     | 20.4%         |
| 50%         | $509     | 17.0%         |

### Sensitivity terhadap Cost Tier

Fill rate fixed φ = 0.80 (moderate assumption):

| Cost Tier | net_avg | P_annual | APY   |
|-----------|---------|----------|-------|
| 0.08%     | 0.398%  | $906     | 30.2% |
| 0.12%     | 0.358%  | $814     | 27.2% |
| 0.20%     | 0.278%  | $633     | 21.1% |

### Full Sensitivity Matrix (APY%)

φ \ cost   | 0.08%  | 0.12%  | 0.20%
-----------|--------|--------|-------
φ = 90%    | 34.0%  | 30.5%  | 23.7%
φ = 80%    | 30.2%  | 27.2%  | 21.1%
φ = 70%    | 26.4%  | 23.8%  | 18.5%
φ = 60%    | 22.6%  | 20.4%  | 15.8%
φ = 50%    | 18.9%  | 17.0%  | 13.2%

### Catatan Penting

1. φ adalah satu-satunya parameter yang tidak bisa di-estimate dari historical data.
   Akan divalidasi di Phase 4 paper trading.

2. `net_avg = 0.358%` adalah average yang mencakup semua coin di universe.
   Coin illiquid (XVG, MTL) mungkin tidak pernah masuk karena dynamic cost filter
   → actual net_avg untuk trades yang benar-benar terjadi bisa lebih tinggi.

3. Capture rate κ = 0.92 adalah theoretical. Jika ada cluster di mana >6 pairs
   spike bersamaan, missed opportunities tidak di-count. Ini sudah termasuk dalam
   κ dari analisis korelasi Phase 1.


---

## BAGIAN 2 — BREAK-EVEN THRESHOLD

### Definisi

Break-even threshold = minimum FR entry agar trade menghasilkan net ≥ 0.

Ada dua level:
1. **Single-settlement break-even**: minimum FR agar 1 settlement hold tidak merugi
2. **Expected break-even**: minimum FR agar E[net] > 0 berdasarkan distribusi hold historis

### Level 1: Single-Settlement Break-even

Hold tepat 1 settlement (8 jam), lalu exit:
```
Gross_1    = FR_entry          (collect 1 payment)
Cost       = cost_rt           (dibayar sekali, saat entry + exit)
Net_1      = FR_entry - cost_rt

Break-even: Net_1 = 0
→ FR_breakeven_1 = cost_rt
```

| Cost Tier | FR Break-even (1 settlement) |
|-----------|------------------------------|
| 0.08%     | 0.08%                        |
| 0.12%     | 0.12%                        |
| 0.20%     | 0.20%                        |

**Implikasi:** Entry threshold 0.05% di bawah break-even untuk cost 0.12% dan 0.20%
pada 1-settlement hold. Ini berarti trades yang exit setelah 1 settlement saja akan rugi
kecuali coin masuk cost tier 0.08%. Ini normal — lihat level 2.

### Level 2: Expected Break-even (Multi-Settlement)

FR tidak flat — ia decay per settlement. Dari Phase 1:
```
Decay ratio per settlement: d = 0.777 (median)
```

Gross dari hold n settlements (geometric series):
```
Gross_n = FR_entry × Σ(d^k, k=0..n-1)
        = FR_entry × (1 - d^n) / (1 - d)
```

Break-even entry FR untuk hold n settlements:
```
FR_min(n) = cost_rt × (1 - d) / (1 - d^n)
           = cost_rt × 0.223 / (1 - 0.777^n)
```

| n (settlements) | FR_min(n) untuk cost 0.12% | FR_min(n) untuk cost 0.20% |
|-----------------|---------------------------|---------------------------|
| 1               | 0.120%                    | 0.200%                    |
| 2               | 0.068%                    | 0.113%                    |
| 3               | 0.050%                    | 0.084%                    |
| 5               | 0.037%                    | 0.062%                    |
| 10              | 0.029%                    | 0.048%                    |

**Untuk expected hold = 5.9 settlements (avg dari Phase 1):**
```
FR_min_expected ≈ 0.035% (cost 0.12%)
FR_min_expected ≈ 0.058% (cost 0.20%)
```

**Ini menjelaskan mengapa entry threshold 0.05% works:**
- Pada cost 0.12%: 0.05% > 0.035% → net positive dalam expectation ✅
- Pada cost 0.20%: 0.05% < 0.058% → net negatif dalam expectation ❌

### Level 3: Strategy-Level Break-even (Dynamic Cost Filter)

Di live, dynamic cost filter menghitung net_expected sebelum setiap entry:
```
net_expected = FR_realtime - cost_rt_realtime

Entry hanya kalau: net_expected > min_profit_threshold
```

Ini adalah break-even real-time. Formula untuk min_profit_threshold:
```
min_profit_threshold = cost_rt + buffer_margin

buffer_margin = minimum acceptable net per trade
              (Phase 2 tidak set angka ini — di-derive Phase 3 dari backtest)
```

Untuk Phase 1 analysis: min_profit_threshold implicitly = 0 (masuk kalau FR > cost).
Dalam practice, lebih baik pakai buffer kecil (misal 0.01%) untuk menghindari
trades yang hanya marginally profitable.

### Ringkasan Break-even per Cost Tier

```
                    Cost 0.08%  Cost 0.12%  Cost 0.20%
Single settlement:  0.080%      0.120%      0.200%
Expected (avg hold):0.023%      0.035%      0.058%
Entry threshold:    0.050%      0.050%      0.050%

Strategy viable?    ✅ yes       ✅ yes       ❌ no
                    (0.05>0.023) (0.05>0.035) (0.05<0.058)
```

Coin dengan cost 0.20% (seperti ADA, NEAR) secara matematis tidak viable pada entry 0.05%.
Dynamic cost filter akan naturally skip mereka kecuali FR spike > 0.058%.


---

## BAGIAN 3 — BUFFER ADEQUACY

### Setup

```
Total capital:        $3,000
Buffer (40%):         $1,200  (tidak di-deploy)
Effective capital:    $1,800  (di-deploy ke 6 pairs)
Per pair:             $300    ($150 spot + $150 futures margin)
Futures notional:     $150    (1x leverage — margin = notional)
```

### Sifat Delta-Neutral: Price Risk Hampir Nol

Posisi delta-neutral: long spot $150 + short futures $150.

Kalau harga bergerak sebesar ΔP:
```
P&L spot    = +$150 × ΔP/P   (long)
P&L futures = -$150 × ΔP/P   (short)
Net P&L     ≈ 0
```

**Dalam konfigurasi ideal, price movement tidak mengancam buffer.**
Buffer bukan untuk melindungi dari price movement — tapi dari dua sumber imperfection:

### Sumber Risiko 1: Basis Divergence

Basis = futures_price - spot_price. Kalau basis diverge, satu leg unrealized loss
tidak fully offset oleh leg lain.

```
Worst-case basis dari Phase 0: 0.1% – 0.5%
Pada $150 position:
  0.5% × $150 = $0.75 per pair
  6 pairs simultaneous worst case: $0.75 × 6 = $4.50

Buffer coverage: $1,200 / $4.50 = 267x worst-case basis event
```

Basis risk hampir tidak mengancam buffer.

### Sumber Risiko 2: Naked Exposure (Partial Fill)

Jika salah satu leg (spot atau futures) tidak ter-fill tapi leg lain sudah fill,
bot harus immediately close leg yang sudah fill (market order). Selama ini terjadi
dalam 60 detik (timeout dari Phase 0), price risk minimal.

Worst case: harga bergerak 5% selama 60 detik (ekstrem):
```
Exposed leg: $150
Loss: $150 × 5% = $7.50 per kejadian

Buffer coverage: $1,200 / $7.50 = 160 kejadian partial fill worst case
```

### Sumber Risiko 3: Funding Rate Adverse

Kalau FR flip setelah entry (posisi open, sekarang kita bayar FR):
```
Avg FR = 0.097% per settlement (Phase 1 entry FR avg)
Loss per settlement if holding wrong direction: $150 × 0.097% = $0.146
6 pairs, 3 settlements sebelum exit: $0.146 × 6 × 3 = $2.62

Buffer coverage: $1,200 / $2.62 = 458 flip events sebelum exhausted
```

### Worst-Case Combined Scenario

Semua 6 pairs kena FR flip bersamaan, hold 5 settlements sebelum exit triggered:
```
Loss = 6 × $150 × 0.097% × 5 = $4.37

Buffer coverage: $1,200 / $4.37 = 275x scenario ini
```

### Kesimpulan Buffer Adequacy

```
Risk source          Worst-case loss    Buffer coverage
─────────────────────────────────────────────────────────
Basis divergence     $4.50              267x
Partial fill (5%)    $7.50/event        160x kejadian
FR flip (5 hold)     $4.37              275x
Combined (semua)     ~$16.37            73x
```

**Buffer 40% ($1,200) sangat adequate untuk semua skenario realistis.**

Satu-satunya skenario yang mengancam buffer secara serius adalah **exchange freeze total**
selama volatilitas ekstrem — di mana posisi tidak bisa di-close dan price diverge jauh dari
entry. Ini adalah tail risk sistemik, bukan sesuatu yang bisa di-hedge dengan buffer biasa.

### Formula Generik Buffer Adequacy

Untuk konfigurasi lain:
```
max_loss_scenario  = sum(futures_notional_i × worst_adverse_rate_i)
buffer_required    = max_loss_scenario × safety_multiplier

Dengan safety_multiplier = 3–5x (konservatif)

Verifikasi: buffer_actual ≥ buffer_required
```

Untuk konfigurasi kita:
```
worst_adverse_rate = 5% (kombinasi basis + FR flip + partial fill)
max_loss           = 6 × $150 × 5% = $45
buffer_required    = $45 × 5 = $225
buffer_actual      = $1,200

$1,200 >> $225 → ADEQUATE dengan margin 5.3x
```


---

## BAGIAN 4 — ABSOLUTE FLOOR (REJECTION CRITERIA)

### Konteks

Dari decisions-phase0.md: rejection criteria existing adalah **relative** (paper trading
yield < 50% dari backtest yield). Ini perlu dilengkapi dengan **absolute floor** — batas
minimum APY yang masih worth the risk, di-derive dari data bukan arbitrary.

### Pendekatan: Worst-Case Scenario dari Data

Absolute floor = APY yang dihasilkan oleh kombinasi input paling pesimis
yang masih realistis (bukan extreme tail).

**Worst realistic inputs:**
```
Cost tier:   0.20%  (tertinggi, berlaku untuk ADA-tier coins)
net_avg:     0.278%  (dari Phase 1 sensitivity: 0.358% - 0.08% cost premium)
Fill rate:   50%    (paling konservatif, untuk coins illiquid)
```

**Menghitung absolute floor APY:**
```
P_trade  = $300 × 0.278% = $0.834
P_annual = 1,030 × 0.92 × 0.50 × $0.834
         = 474 × $0.834
         = $395

APY_floor = $395 / $3,000 = 13.2%
```

**Absolute floor = 13.2% APY on total capital ($3,000)**

### Interpretasi

```
APY ≥ 30%      → Strong performance (φ ≥ 80%, cost ≤ 0.12%)
APY 20%–30%    → Acceptable
APY 13.2%–20%  → Marginal — investigate cost dan fill rate lebih dalam
APY < 13.2%    → REJECT — bahkan worst-case assumption tidak terpenuhi
                  Artinya actual performance lebih buruk dari pessimistic floor
```

### Mengapa 13.2%, Bukan Angka Lain?

Angka ini adalah output dari dua layer worst case:
1. Cost 0.20% = tier tertinggi dari 3 tiers yang di-define di Phase 0
2. Fill rate 50% = lower bound dari range yang di-estimate (50–90%)

Bukan arbitrary — ini adalah **p10 scenario dari parameter space** yang sudah
di-define di Phase 0–1. Kalau actual APY di bawah ini, berarti salah satu:
- Ada hidden cost yang lebih besar dari semua 3 tiers (structural problem)
- Fill rate lebih rendah dari 50% (execution fundamentally broken)
- Frequency of opportunity < theoretical (market regime berubah)

Semua tiga → strategy tidak viable, bukan sekadar underperformance.

### Benchmark untuk Konteks

```
Risk-free alternatives (2026 estimate):
  US Treasury:        ~4.5%
  Stablecoin yield:   ~6–8%

Absolute floor (13.2%) = 1.7x–2.9x risk-free
→ Masih memberikan meaningful risk premium, tapi tipis

Jika APY < 13.2%:
  Risk premium = negatif atau tidak meaningful
  → Better off di stablecoin yield, tanpa operational complexity
```

### Update Rejection Criteria

Existing di Phase 0 Bagian 6:
```
4. Paper trading annualized yield % < 50% dari backtest → reject
```

Dengan tambahan:
```
4a. Paper trading APY < 50% dari backtest → reject  [existing, relative]
4b. Paper trading APY < 13.2% annualized  → reject  [new, absolute floor]

Keduanya harus dipenuhi. Jika salah satu gagal → reject.
```

---

## BAGIAN 5 — RINGKASAN FORMULA

### Formula Canonical

```
1. APY = T × κ × φ × [(1 - b) / S] × net_avg

   Variabel tetap (dari Phase 0–1):
   T = 1,030    κ = 0.92    b = 0.40    S = 6    C = $3,000

   Variabel bergerak:
   φ = fill rate     (divalidasi Phase 4)
   cost_rt = per-coin cost tier (0.08%, 0.12%, atau 0.20%)
   FR_avg  = fungsi entry threshold (0.358% net pada threshold 0.05%, cost 0.12%)

2. FR_min(n) = cost_rt × (1 - d) / (1 - d^n)
   d = 0.777 (decay per settlement)
   n = expected hold settlements

   Simplified (entry filter praktis):
   FR_entry ≥ cost_rt   [guarantee break-even pada 1 settlement]
   FR_entry ≥ 0.05%     [chosen threshold, viable untuk avg hold 5.9 settlements]

3. Buffer adequacy:
   buffer_required = max_loss_scenario × safety_multiplier (5x)
   max_loss_scenario = Σ(futures_notional_i × worst_adverse_rate_i)

   Untuk konfigurasi ini:
   max_loss = 6 × $150 × 5% = $45
   buffer_required = $225
   buffer_actual = $1,200   → adequate (5.3x margin)

4. Absolute floor:
   APY_floor = T × κ × φ_min × [(1-b)/S] × net_avg_worst
             = 1,030 × 0.92 × 0.50 × (0.60/6) × 0.00278
             = 13.2%

   Reject jika paper trading APY < 13.2%
```

---

## STATUS DOKUMEN

```
DRAFT v1.0 — 22 May 2026
Pending review oleh Maou

Next step setelah approved:
→ Phase 3: Backtest
  - Code struktur production
  - Simulate entry/exit dengan dynamic cost model
  - Stress test: LUNA crash, FTX collapse, BTC Aug 2024
  - Validate actual yield vs formula Phase 2
```
