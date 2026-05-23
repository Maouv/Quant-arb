# PHASE 3 BACKTEST — IMPLEMENTATION SPEC
**Date:** 23 May 2026
**Status:** FINAL — approved by Maou
**Author:** Maou + Kiro
**Depends on:** phase0.md, phase1.md, phase2.md, phase3-requirements.md

---

## QUICK CONTEXT (baca ini dulu)

Strategy: funding rate arbitrage — long spot + short futures saat FR tinggi, collect funding payment
setiap 8 jam, exit saat FR turun. Delta-neutral: tidak ada directional price bet.

Phase 3 goal: simulate strategy di training data (2022–2024), validate yield vs formula Phase 2,
stress test tiga crash periods, analisis drawdown dan regime.

Data yang tersedia: HANYA funding rate per coin per 8h. Tidak ada OHLCV. Price movement
di-abstrak ke flat cost tier karena posisi delta-neutral.

Backtest ini untuk TRAINING SET SAJA. Validation set (2025) tidak boleh dibuka.

---

## CODING STANDARDS — WAJIB DIIKUTI

- Python 3.12
- PEP8 untuk semua code
- Naming: camelCase untuk variabel dan fungsi, PascalCase untuk class
- Tidak boleh ada magic number — semua parameter di config.py
- Tidak boleh ada silent exception (bare `except:` dilarang)
- Setiap fungsi maksimal 30 baris — pecah kalau lebih
- Pure functions di mana memungkinkan (tidak ada hidden state)
- Tidak ada print() di engine — pakai logging module
- Type hints wajib untuk semua fungsi
- Docstring wajib untuk semua fungsi dan class

Contoh style yang benar:
```python
def calculateNetYield(grossYield: float, costRt: float) -> float:
    """Calculate net yield after round-trip cost."""
    return grossYield - costRt
```

---

## STRUKTUR FOLDER

```
phase3_backtest/
├── config.py                   # SEMUA parameter di sini
├── run_backtest.py             # entrypoint
├── engine/
│   ├── __init__.py
│   ├── data_loader.py          # load + validate FR data
│   ├── simulator.py            # core event loop
│   ├── portfolio.py            # slot management + accounting
│   └── cost_model.py           # cost assignment per coin
├── analysis/
│   ├── __init__.py
│   ├── monthly.py              # rolling monthly stats
│   ├── stress_test.py          # crash windows × multipliers
│   ├── decay_validator.py      # predicted vs actual gross
│   └── drawdown.py             # max DD, consecutive losses, recovery
└── tests/
    ├── __init__.py
    ├── test_accounting.py
    ├── test_causality.py
    ├── test_stress.py
    └── test_edge_cases.py
```

---

## config.py — LENGKAP

Semua nilai berikut harus ada di config.py persis seperti ini:

```python
# --- Data ---
DATA_PATH            = "./funding_rate_data_8h_expanded/"
TRAINING_START       = "2022-01-01"
TRAINING_END         = "2024-12-31"
MIN_TRAINING_MONTHS  = 18
EXCLUDED_SYMBOLS     = ["NEARUSDT"]   # structural cost > yield, keputusan Phase 0

# --- Strategy ---
ENTRY_THRESHOLD      = 0.05    # % per settlement, |FR| >= ini untuk entry signal
EXIT_THRESHOLD       = 0.02    # % per settlement, |FR| < ini untuk exit signal

# --- Portfolio ---
TOTAL_CAPITAL        = 3000.0
BUFFER_RATIO         = 0.40
MAX_PAIRS            = 6
# effective_capital  = TOTAL_CAPITAL * (1 - BUFFER_RATIO) = 1800.0
# size_per_pair      = effective_capital / MAX_PAIRS       = 300.0

# --- Cost Model ---
# 10 coins dengan actual cost dari Phase 0 sampling
ACTUAL_COSTS = {
    "ETHUSDT":  0.0814,
    "ZECUSDT":  0.0882,
    "XRPUSDT":  0.1018,
    "DOGEUSDT": 0.1088,
    "LINKUSDT": 0.1113,
    "SUIUSDT":  0.1119,
    "AAVEUSDT": 0.1275,
    "INJUSDT":  0.1562,
    "UNIUSDT":  0.1773,
    "ADAUSDT":  0.2002,
}
# 90 coin sisanya pakai tier — backtest dijalankan 3x
COST_TIERS = {"low": 0.08, "mid": 0.12, "high": 0.20}

# --- Stress Test ---
STRESS_MULTIPLIERS = [2, 3, 4, 5, 6]
STRESS_WINDOWS = {
    "LUNA": ("2022-05-01", "2022-05-31"),
    "FTX":  ("2022-11-01", "2022-11-30"),
    "BTC":  ("2024-08-01", "2024-08-31"),
}
RECOVERY_DAYS = 90

# --- Decay Model (dari Phase 1) ---
DECAY_RATIO = 0.777  # median decay per settlement

# --- Fragility Analysis ---
SHORT_HOLD_THRESHOLD = 3  # settlements — trades <= ini di-analisis terpisah
```

---

## DATA FORMAT

File: `./funding_rate_data_8h_expanded/{SYMBOL}-fundingRate.csv`
Kolom:
- `calc_time` — int64, Unix timestamp milliseconds UTC
- `funding_interval_hours` — int, selalu 8
- `last_funding_rate` — float, dalam desimal (0.0001 = 0.01%)

Penting: `last_funding_rate` harus dikalikan 100 untuk convert ke persen.

Total files: 108
Files yang tidak valid sebagai FR data: `_phase1_results.csv`, `_summary.csv` — skip.
Coins yang di-exclude karena < 18 bulan training: AGLDUSDT, ARKMUSDT, BICOUSDT, BNTUSDT,
PENDLEUSDT, SEIUSDT, WLDUSDT.
Coins yang di-exclude by rule: NEARUSDT.
Universe backtest: 100 coins.

---

## CORE ENGINE — ATURAN KAUSAL (NON-NEGOTIABLE)

### Rule 1: t+1 Enforcement
FR di index t HANYA BOLEH trigger action di index t+1. TIDAK BOLEH di t.

```
timeline:
  t=0: FR = 0.08% (>= 0.05% entry threshold) → SIGNAL
  t=1: Entry terjadi di sini. Gross collection dimulai dari FR[t=1].
  t=2: FR = 0.06% → masih hold, collect FR[t=2]
  t=3: FR = 0.015% (< 0.02% exit threshold) → SIGNAL EXIT
  t=4: Exit terjadi di sini. FR[t=3] TIDAK di-collect (sudah di bawah threshold).

gross = FR[t=1] + FR[t=2]   ← hanya settlements SELAMA posisi open
cost  = cost_rt              ← dikurangi SEKALI saat exit
net   = gross - cost
```

Konsekuensi penting: Phase 1 menghitung gross TERMASUK FR di settlement trigger (t=0).
Phase 3 tidak. Ini menyebabkan Phase 3 yield lebih rendah dari Phase 1.
Magnitude perbedaan ini HARUS dihitung dan dilaporkan di output sebagai
"Phase 1 vs Phase 3 yield reconciliation".

### Rule 2: Entry dan exit tidak boleh di candle yang sama
Minimum hold = 1 settlement.

### Rule 3: Gap data = break posisi
Kalau ada missing settlement di tengah hold, posisi di-close di settlement
terakhir sebelum gap. Gross yang sudah di-collect tetap dihitung.

---

## SIMULATOR LOGIC — PSEUDOCODE

```
untuk setiap settlement t dari t=0 sampai t=N-1:
    
    1. CLOSE posisi yang trigger exit di t-1:
       untuk setiap posisi open:
           kalau FR[t-1] < EXIT_THRESHOLD → close di t, realisasi PnL
    
    2. BUKA posisi baru dari signal di t-1:
       kalau slot < MAX_PAIRS:
           kandidat = coins yang FR[t-1] >= ENTRY_THRESHOLD
                      dan belum punya posisi open
           sort kandidat by (FR[t-1] - cost) descending
           tie-break: alphabetical by symbol
           ambil top N sesuai slot available
           untuk setiap kandidat terpilih:
               buka posisi mulai t, entry_fr = FR[t-1]
    
    3. COLLECT FR untuk SEMUA posisi open (termasuk yang baru dibuka di step 2):
       untuk setiap posisi open:
           gross += FR[t]   ← collect FR settlement ini
```

Urutan di atas PENTING: close → open → collect.
Alasan: funding dibayar ke siapa yang hold posisi SAAT settlement terjadi.
Entry di t berarti sudah in position untuk settlement t, jadi berhak collect FR[t].
Ini juga mencegah slot collision dan accounting error.

---

## COST MODEL

### Fungsi utama

```python
def getCostForSymbol(symbol: str, tier: str) -> float:
    """
    Return round-trip cost % untuk symbol.
    Kalau symbol punya actual Phase 0 cost → pakai itu.
    Kalau tidak → pakai tier (low/mid/high).
    """
```

### Running backtest 3x

Backtest dijalankan tiga kali dengan tier berbeda untuk 90 coin yang tidak punya actual cost:
- Run 1: tier = "low" (0.08%)
- Run 2: tier = "mid" (0.12%)
- Run 3: tier = "high" (0.20%)

10 coin dengan actual Phase 0 cost selalu pakai angka aktualnya di semua run.
Output akhir = tiga set hasil (low/mid/high) sebagai range.

---

## STRESS TEST

### Crash windows
```
LUNA: 2022-05-01 — 2022-05-31
FTX:  2022-11-01 — 2022-11-30
BTC:  2024-08-01 — 2024-08-31
```

### Cost multiplier logic
- Multipliers: [2, 3, 4, 5, 6]
- Applied ke: settlements yang jatuh DALAM crash window
- Anchor: settlement pertama yang jatuh dalam window (bukan dari settlement ke-2 entry)
- Trades entry sebelum window, exit dalam window: cost naik dari hari pertama window
- Trades entry dalam window, exit setelah window: cost normal setelah window ends
- Trades di luar window: cost tidak berubah

### Mid-position cost spike
Untuk setiap trade dengan hold >= 2 settlements, simulasikan cost naik mulai
dari settlement pertama dalam crash window (kalau trade sedang open saat window dimulai).

```python
def stressMidPositionCost(trades: list, multiplier: float, windowStart: pd.Timestamp,
                           windowEnd: pd.Timestamp) -> list:
    """
    Recalculate net untuk trades yang overlap dengan crash window.
    Cost settlement dalam window = cost_original * multiplier.
    Cost settlement di luar window = cost_original.
    Returns list trade dengan net yang sudah di-adjust.
    """
```

### Output per crash window

```
=== [WINDOW NAME] STRESS TEST ===
Period: YYYY-MM-DD to YYYY-MM-DD

--- SURVIVAL ---
Trades dalam window:        N
Trades/day window vs normal: X vs Y
Net yield (1x cost):        $A
Net yield (2x cost):        $B
Net yield (3x cost):        $C
Net yield (4x cost):        $D
Net yield (5x cost):        $E
Net yield (6x cost):        $F
Break-even multiplier:      Nx
Avg hold dalam window:      X settlements vs Y (normal)
Hold=1 rate dalam window:   X% vs Y% (normal)
Peak concurrent spikes:     N coins
Slot saturation rate:       X% of settlements
Missed trades (slot full):  N
Mid-position 3x survival:   X% trades
Mid-position 5x survival:   X% trades

--- RECOVERY (90 hari setelah window) ---
Max drawdown:               $X (Y%)
Max drawdown duration:      N days
Recovery time:              N days [atau "unrecovered in 90d"]
Max consecutive losses:     N trades
Max consecutive neg days:   N days
Yield recovery day 1-30:    avg $X/trade
Yield recovery day 31-60:   avg $X/trade
Yield recovery day 61-90:   avg $X/trade
Trend:                      [improving/flat/deteriorating]
```

### Cross-window comparison
Setelah tiga windows: ranking by max drawdown, ranking by recovery time,
maximum cost tolerance (multiplier di mana strategi tidak survive salah satu crash).

---

## ANALISIS WAJIB

### 1. Rolling Monthly Stats
- Trades per bulan
- Win rate per bulan
- Avg net yield per bulan
- T (opportunity count) per bulan
- Flag bulan di mana T drop > 30% dari median
- Flag bulan di mana win rate < 40%

### 2. Decay Model Validation
Predicted gross dari model geometric (d=0.777) vs actual gross per hold bucket.

```
Hold bucket | Predicted gross% | Actual gross% | Gap% | Gap driver
hold = 1    |                  |               |      |
hold = 2    |                  |               |      |
hold = 3    |                  |               |      |
hold = 4-6  |                  |               |      |
hold = 7-10 |                  |               |      |
hold = 11+  |                  |               |      |
```

Formula predicted: `gross_predicted = FR_entry × (1 - d^n) / (1 - d)`
di mana d = 0.777, n = hold length, FR_entry = FR di settlement trigger (t).

### 3. Hold Fragility Analysis
Trades dengan hold <= 3 settlements: apakah aggregate net positif atau negatif?
Ini validasi structural weakness yang diidentifikasi Phase 2.

### 4. Min Profit Threshold Derivation
Dari distribusi net per trade, derive minimum net_expected per trade
yang masih contribute positively setelah accounting for variance.
Candidate: 0.01% buffer di atas break-even.

### 5. Phase 1 vs Phase 3 Yield Reconciliation
Quantify exact magnitude overstate Phase 1 akibat t+1 enforcement.
Formula: overstate per trade = (entry_fr - entry_collect_fr) / 100 × size_per_pair
Alasan: Phase 3 tetap collect FR[t+1], hanya kehilangan selisih FR[t] - FR[t+1].
Total overstate = sum(entry_fr - entry_collect_fr) / 100 × 300 untuk semua trades.

---

## TRADE LOG FORMAT

Setiap trade harus punya fields berikut:

```python
{
    "trade_id":            str,   # f"{symbol}_{entry_time}"
    "symbol":              str,
    "side":                str,   # "long_spot_short_futures" atau "short_spot_long_futures"
    "entry_time":          pd.Timestamp,
    "exit_time":           pd.Timestamp,
    "entry_fr":            float, # FR di settlement trigger (t), dalam %
    "entry_collect_fr":    float, # FR di t+1 (pertama yang di-collect), dalam %
    "exit_fr":             float, # FR saat exit trigger
    "hold_settlements":    int,   # jumlah settlements posisi open
    "gross_pct":           float, # sum |FR| selama hold, dalam %
    "cost_rt_pct":         float, # round-trip cost yang dipakai, dalam %
    "net_pct":             float, # gross - cost, dalam %
    "gross_dollar":        float, # gross_pct / 100 * size_per_pair
    "cost_dollar":         float,
    "net_dollar":          float,
    "cost_tier":           str,   # "actual", "low", "mid", atau "high"
    "gap_closed":          bool,  # True kalau posisi di-close karena data gap
}
```

---

## EQUITY CURVE FORMAT

Per settlement timestep:

```python
{
    "timestamp":       pd.Timestamp,
    "balance":         float,   # realized cash
    "unrealized_pnl":  float,   # sum gross dari posisi open (belum dikurangi cost)
    "equity":          float,   # balance + unrealized_pnl
    "drawdown_dollar": float,   # equity - peak_equity (negatif kalau DD)
    "drawdown_pct":    float,   # drawdown_dollar / peak_equity * 100
    "open_positions":  int,     # jumlah posisi open
    "exposure":        float,   # total capital deployed
}
```

---

## TESTS — HARUS SELESAI SEBELUM ENGINE JALAN

### test_accounting.py

```
T-ACC-01: cost_rt dikurangi tepat sekali per trade, bukan per settlement
T-ACC-02: gross = sum |FR| selama hold sebelum cost
T-ACC-03: net = gross - cost, tidak lebih tidak kurang
T-ACC-04: open_positions tidak pernah > MAX_PAIRS = 6
T-ACC-05: total exposure tidak pernah > effective_capital = 1800.0
T-ACC-06: P&L dua trades yang overlap tidak saling mempengaruhi
```

Cara test T-ACC-01 sampai T-ACC-03: inject synthetic FR sequence yang diketahui,
verify trade log output match expected values manual.

### test_causality.py

```
T-CAU-01: FR di index t tidak trigger entry di t — harus t+1
T-CAU-02: Entry dan exit tidak terjadi di settlement yang sama
T-CAU-03: Gross hanya dari FR settlements SELAMA posisi open (bukan sebelum entry)
T-CAU-04: Posisi tidak pernah "tahu" FR masa depan
```

Cara test: buat DataFrame kecil dengan FR sequence yang diketahui,
run simulator, verify entry_time > signal_time.

Contoh synthetic sequence untuk T-CAU-01:
```
t=0: FR=0.08% → signal
t=1: entry → collect FR[1]=0.07%
t=2: FR=0.01% → exit signal
t=3: exit → gross = 0.07% (bukan 0.08%+0.07%)
```

### test_stress.py

```
T-STR-01: Multiplier applied ke semua settlements dalam window, bukan cherry-pick
T-STR-02: Settlements di luar window tidak ter-affect
T-STR-03: Mid-position spike anchor = hari pertama window, bukan settlement ke-2 entry
T-STR-04: Trade entry dalam window, exit setelah window → cost normal setelah window
T-STR-05: Trade entry sebelum window, exit dalam window → cost naik dari hari pertama window
```

### test_edge_cases.py

```
T-EDG-01: Data gap di tengah hold → posisi close di settlement terakhir sebelum gap
T-EDG-02: Semua 6 slot penuh → opportunity baru di-reject, tidak ada eviction
T-EDG-03: FR flip dalam 1 settlement → exit signal di t, exit eksekusi di t+1
T-EDG-04: Coin dengan data < 18 bulan → di-skip seluruhnya (tidak partial)
T-EDG-05: Tie-break saat sort kandidat → alphabetical, hasil deterministik
T-EDG-06: FR tepat sama dengan threshold (FR = 0.05%) → dihitung sebagai entry signal
T-EDG-07: FR tepat sama dengan exit threshold (FR = 0.02%) → TIDAK trigger exit
          (exit hanya kalau FR < 0.02%, bukan <=)
```

---

## RUN ORDER

```
1. python -m pytest tests/           ← semua tests harus pass sebelum lanjut
2. python run_backtest.py --tier low
3. python run_backtest.py --tier mid
4. python run_backtest.py --tier high
```

Output ketiga run disimpan di folder `results/` dengan nama:
`trade_log_{tier}.csv`, `equity_curve_{tier}.csv`, `report_{tier}.txt`

---

## GUARDRAILS — DILARANG KERAS

- Jangan buka file di path `./funding_rate_data_8h_expanded/` yang berisi kata "2025"
  dalam timestamp (validation set contamination)
- Jangan pakai `.iloc[t]` untuk lookup FR — selalu gunakan timestamp-based indexing
  untuk menghindari off-by-one yang silent
- Jangan interpolate missing settlements — gap = break posisi
- Jangan fabricate fill prices — tidak ada price data, tidak ada fill price di trade log
- Jangan optimize parameter (entry/exit threshold) — nilai sudah fixed dari Phase 1
- Jangan run analysis pada validation set (2025) — training end = 2024-12-31

---

## KNOWN LIMITATIONS (dokumentasikan di output)

1. t+1 enforcement menyebabkan yield lebih rendah dari Phase 1 — ini benar secara kausal
2. Cost model flat — tidak capture spread widening intraday
3. Fill rate diasumsikan 100% di backtest — Phase 4 paper trading yang validate actual fill rate
4. Survivorship bias — 7 coins yang delist/ineligible tidak ter-include, yield mungkin sedikit overstated
5. Tidak ada orderbook data — slippage tidak bisa disimulasi secara akurat, hanya di-approximate via cost tier

---

## SETELAH BACKTEST SELESAI

Setelah tiga run (low/mid/high) selesai dan output tersedia:
1. Kembali ke agent utama untuk review hasil
2. Agent utama akan spawn sub-agent untuk adversarial audit:
   - Execution Realism agent: review apakah asumsi fill dan timing realistic
   - Validation agent: cross-check accounting dan causality dari output
3. Baru setelah audit selesai → validation set 2025 dibuka SATU KALI

---

## STATUS

```
FINAL — approved 23 May 2026
Ready for implementation
```
