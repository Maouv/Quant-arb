# PHASE 4 HANDOFF — 02: REQUIREMENTS
**Date:** 23 May 2026

---

## TUJUAN PHASE 4

Bukan profit. Validate 3 hal yang tidak bisa divalidasi di backtest:
1. **Fill rate actual** per coin (backtest assume 100%)
2. **Cost actual** per coin real-time (backtest pakai flat tier)
3. **Bot execution correctness** (orphan orders, timing, race conditions)

Minimum durasi: 4–6 minggu non-stop.

---

## CODING STANDARDS

- Python 3.12
- PEP8
- camelCase untuk variabel dan fungsi
- PascalCase untuk class
- Type hints wajib semua fungsi
- Docstring wajib semua fungsi dan class
- Max 30 baris per fungsi — pecah kalau lebih
- Semua parameter di config.py — tidak ada magic number di code
- Tidak ada bare `except:` — semua exception explicit
- Tidak ada `print()` di bot — pakai logging module

---

## REPO STRUCTURE

Buat repo baru bernama `quant-arb-bot`. TERPISAH dari `/root/quant-arb/`.

```
quant-arb-bot/
├── config/
│   ├── config.py           # semua parameter (lihat section CONFIG di bawah)
│   └── secrets.env         # API keys — JANGAN di-commit ke git
├── bot/
│   ├── main.py             # entrypoint, clock-aligned cycle loop
│   ├── scanner.py          # scan FR semua coins, hitung net_expected
│   ├── executor.py         # place/cancel orders, verify fills
│   ├── position_manager.py # monitor posisi open, orphan check, collect FR
│   └── risk_guard.py       # pre-entry checks, cost spike guard
├── data/
│   └── cost_cache.py       # cache + fetch real-time cost per coin
├── logs/                   # semua log file disimpan di sini
│   └── .gitkeep
├── tests/
│   ├── test_connectivity.py  # verify semua API endpoints accessible
│   └── test_executor.py      # unit test order logic
├── .gitignore              # wajib include: secrets.env, logs/, __pycache__/
└── requirements.txt        # ccxt==4.2.86 (LOCKED), requests, python-dotenv
```

---

## CONFIG — SEMUA NILAI WAJIB ADA

```python
# config/config.py

# --- Mode ---
USE_TESTNET: bool = True        # False hanya saat Phase 5 live
CONFIRM_MAINNET: bool = False   # Wajib True sebelum Phase 5

# --- Binance API ---
# Diload dari secrets.env, BUKAN hardcode di sini
# import os; API_KEY = os.getenv("BINANCE_API_KEY")

# --- Universe ---
# NEARUSDT excluded secara permanen (keputusan Phase 0: cost struktural > yield)
# Coins lain TIDAK di-hardcode excluded — dynamic cost filter yang handle
EXCLUDED_SYMBOLS: list[str] = ["NEARUSDT"]

# --- Strategy (LOCKED — tidak boleh diubah tanpa trial registry) ---
ENTRY_THRESHOLD: float = 0.05   # % |FR| >= ini untuk entry signal
EXIT_THRESHOLD: float  = 0.02   # % |FR| < ini untuk exit signal

# --- Portfolio (LOCKED) ---
TOTAL_CAPITAL: float   = 3000.0   # referensi saja — actual balance di-fetch dari API
BUFFER_RATIO: float    = 0.40
MAX_PAIRS: int         = 6
# PENTING: EFFECTIVE_CAPITAL dan SIZE_PER_PAIR TIDAK di-hardcode
# Di-compute dari actual balance saat startup:
#   effectiveCapital = getAvailableBalance() * (1 - BUFFER_RATIO)
#   sizePerPair      = effectiveCapital / MAX_PAIRS

# --- Execution ---
ORDER_TIMEOUT_SECONDS: int   = 60       # timeout limit order sebelum cancel
CYCLE_INTERVAL_MINUTES: int  = 5        # cycle setiap 5 menit
BLACKOUT_MINUTES: int        = 5        # blackout sebelum settlement
SETTLEMENT_HOURS_UTC: list[int] = [0, 8, 16]

# --- Cost model ---
# Di live, cost selalu dihitung real-time dari orderbook — BUKAN dari nilai ini
# ACTUAL_COSTS dari Phase 0 adalah snapshot satu hari, tidak valid sebagai baseline permanen
# isCostSpike() dan isBroadMarketStress() compare terhadap rolling average
# yang di-observe selama bot jalan (disimpan di cost_cache.py)
DEFAULT_COST_TIER: float = 0.12   # fallback awal sebelum rolling average terbentuk
                                   # diganti rolling average setelah N observations

# --- Risk guards ---
COST_SPIKE_MULTIPLIER: float  = 3.0   # stop entry kalau cost > 3x normal
BROAD_STRESS_THRESHOLD: float = 0.50  # stop entry kalau >50% coins elevated cost
MIN_PROFIT_THRESHOLD: float   = 0.01  # % minimum net_expected sebelum entry

# --- Fees (Binance) ---
TAKER_FEE: float = 0.04   # % per side
FEE_RT: float    = 0.08   # % round trip (2 × taker_fee)

# --- Rejection criteria (dari Phase 0) ---
PAPER_APY_ABSOLUTE_FLOOR: float  = 13.2   # % — reject kalau di bawah ini
PAPER_APY_RELATIVE_FLOOR: float  = 0.50   # 50% dari backtest APY
BACKTEST_APY_MID: float          = 28.0   # % — dari Phase 3 results_v2
```

---

## BOT CYCLE — URUTAN WAJIB

Setiap cycle (setiap 5 menit, clock-aligned):

```
STEP 0 — SAFETY CHECKS
→ isBlackoutWindow()? → skip entry saja, monitoring tetap jalan
→ isBroadMarketStress()? → skip entry semua coins

STEP 1 — FETCH DATA (parallel untuk semua coins)
→ GET /fapi/v1/premiumIndex (semua coins sekaligus)
   → lastFundingRate = FR terakhir yang settled
   → nextFundingTime = kapan settlement berikutnya
→ GET /fapi/v1/ticker/bookTicker (semua coins sekaligus)
→ GET /api/v3/ticker/bookTicker (semua coins sekaligus)
→ GET /fapi/v1/positionRisk (posisi yang sedang open)

STEP 2 — MONITOR POSISI EXISTING
→ Untuk setiap posisi open:
   Cek apakah FR sudah < EXIT_THRESHOLD → tandai untuk exit normal (limit order)
   Cek apakah FR sudah flip sign (positif → negatif atau sebaliknya) → emergency exit
   Orphan check (regular + algo orders)
→ Exit normal: limit order di mid price, timeout 60 detik
→ Emergency exit (FR flip): market order langsung — execution lebih penting dari cost
→ Execute exits yang ditandai

STEP 3 — CARI OPPORTUNITY BARU
→ Hanya kalau slot < MAX_PAIRS
→ Untuk setiap coin tanpa posisi open:
   Hitung total_rt_cost dari real-time orderbook (lihat section REAL-TIME COST CALCULATION)
   — BUKAN flat tier, BUKAN hardcode — harus dari spread + slippage + basis saat itu
   Hitung net_expected = |lastFundingRate| - total_rt_cost
   Filter: net_expected > MIN_PROFIT_THRESHOLD   ← strict >, bukan >=, sesuai Phase 0
   Filter: isCostSpike() == False
→ Sort by net_expected descending
→ Tie-break: alphabetical by symbol (deterministic)
→ Ambil top N sesuai slot available

Note: live akan punya lebih sedikit trades dari backtest karena dynamic cost filter
aktif pre-trade. Backtest tidak punya filter ini — entry hanya dari FR threshold.
Ini expected behavior, bukan bug.

STEP 4 — EXECUTE ENTRY (LANGSUNG, tidak tunggu settlement)
→ Entry sesegera mungkin setelah signal terdeteksi
→ Tidak perlu tunggu 8 jam — ini berbeda dari backtest
→ Backtest pakai t+1 karena keterbatasan data 8h snapshot
→ Live bot entry kapan saja dalam window 8 jam, kecuali blackout 5 menit terakhir
→ Place spot + futures order bersamaan (limit, mid price)
→ Monitor fill setiap 5 detik, timeout 60 detik
→ Kalau salah satu tidak fill → cancel keduanya, log failed attempt
→ Kalau keduanya fill → place SL/TP via algo order
→ Verify SL/TP terpasang
→ Log semua

STEP 5 — ORPHAN CHECK
→ Get open regular orders
→ Get open algo orders (endpoint terpisah)
→ Order tanpa matching position → cancel immediate
→ Position tanpa SL/TP → log critical alert
```

**Catatan penting: Live vs Backtest timing**
- Backtest: entry di t+1 (8 jam setelah FR signal) — keterbatasan data snapshot 8h
- Live: entry langsung saat signal terdeteksi dalam cycle 5 menit
- Konsekuensi: live bisa collect FR di settlement terdekat, backtest tidak
- Ini adalah salah satu alasan live yield bisa lebih tinggi dari backtest

---

## UNIVERSE — INCLUSION CRITERIA

Bot hanya trade coins yang memenuhi semua kriteria berikut:
```
1. Listed di Binance dengan KEDUANYA: spot pair USDT + perpetual futures USDT-margined
2. Funding interval: 8 jam SAJA — bukan 4 jam
3. Minimum funding rate history: 18 bulan (dari training set)
4. Bukan stablecoin atau wrapped token
5. Bukan NEARUSDT (excluded permanen — cost struktural > yield, keputusan Phase 0)
```

**Volume filter tidak diimplementasikan.** Alasan:
- Look-ahead bias: volume data hari ini tidak valid untuk filter training 2022-2024
- Redundant: dynamic cost filter real-time sudah handle illiquid coins secara otomatis
- Historical volume data tidak tersedia tanpa download OHLCV tambahan

Illiquid coins akan naturally excluded oleh dynamic cost filter karena
spread mereka terlalu lebar → net_expected < MIN_PROFIT_THRESHOLD → skip.

**⚠️ Tradeoff yang harus disadari:**
Drop volume filter acceptable HANYA kalau dynamic cost filter berjalan benar.
Kalau ada bug di cost calculation → bot bisa entry ke coins dengan $50K volume/day
dan spread 2-3% yang seharusnya di-skip.

**Test wajib di Phase 4 paper trading:**
```
1. Verify: coins dengan spread > 0.5% tidak pernah ter-entry
2. Verify: log menunjukkan coins illiquid di-skip dengan alasan "net_expected < threshold"
3. Verify: tidak ada trades di coins dengan volume < $1M/day
   (cek post-hoc dari trade log — bukan pre-filter)
```

**Mengapa hanya 8 jam, tidak expand ke 4 jam:**
- 4h coins belum punya historical data yang cukup di training set
- Cost model belum di-validate untuk coins tersebut
- Expand ke 4h = Phase 5 territory, setelah 8h proven di live

Universe tidak perlu di-hardcode sebagai list — bot scan semua coins yang eligible
dari Binance API saat startup, filter berdasarkan kriteria di atas.

---

## STARTUP SEQUENCE (setiap bot start/restart)

```
1. Load config dan secrets dari secrets.env
2. Verify USE_TESTNET flag — jangan salah deploy ke mainnet
3. Fetch actual balance dari API → hitung effectiveCapital dan sizePerPair
4. Fetch min notional semua coins dari GET /fapi/v1/exchangeInfo
   → Simpan di memory, tidak perlu fetch ulang setiap cycle
   → Validate: sizePerPair >= min_notional setiap coin sebelum entry
5. Fetch open positions → reconcile dengan trade log
6. Place emergency SL untuk posisi yang tidak punya SL/TP
7. Log downtime kalau ini adalah restart (bukan fresh start)
8. Tunggu clock-aligned cycle boundary
9. Mulai cycle normal
```

---

## IDLE CAPITAL RULE

Kalau hanya 4 pair yang masuk threshold, sisa 2 slot IDLE.
```
Tidak ada re-allocation ke pair yang sudah open
Tidak ada exception
Idle capital = buffer, bukan waste
sizePerPair tetap = effectiveCapital / MAX_PAIRS (bukan / jumlah_pair_aktif)
```

---

## POSITION SYMBOL FORMAT

```python
# ccxt unified format (untuk ccxt calls):
pos['symbol']        → 'ETH/USDT:USDT'

# Binance raw format (untuk API calls langsung):
pos['info']['symbol'] → 'ETHUSDT'

# SELALU pakai raw format untuk API calls
# SELALU pakai unified format untuk ccxt calls
```

---

## RATE LIMITING

```
Binance limits:
  Spot:    1,200 request weight/menit
  Futures: 2,400 request weight/menit

100 coins × multiple calls per cycle = ratusan requests.

Wajib:
1. Pakai batch endpoints — 1 call return semua coins sekaligus:
   GET /fapi/v1/premiumIndex      → FR semua coins (1 call)
   GET /fapi/v1/ticker/bookTicker → bid/ask futures semua (1 call)
   GET /api/v3/ticker/bookTicker  → bid/ask spot semua (1 call)

2. Order book depth hanya fetch untuk KANDIDAT entry saja,
   bukan untuk semua 100 coins setiap cycle.
   Kandidat = coins yang sudah lolos FR threshold dari premiumIndex.

3. Jangan fetch depth kalau semua 6 slot sudah penuh.
```

---

## MAINNET GUARD

```python
# Di main.py sebelum bot mulai — wajib ada
if not USE_TESTNET:
    assert CONFIRM_MAINNET, (
        "CONFIRM_MAINNET harus True sebelum deploy ke mainnet. "
        "Set di config.py setelah review manual."
    )
# Setelah ganti USE_TESTNET=False → WAJIB restart bot
# Jangan hot-reload config di runtime untuk flag ini
```

---

## CLOCK-ALIGNED CYCLE

```python
from datetime import datetime, timezone
import time

def waitForNextCycle(intervalMinutes: int = 5) -> None:
    """Wait until next clock-aligned cycle boundary."""
    now = datetime.now(timezone.utc)
    secondsToWait = (intervalMinutes - now.minute % intervalMinutes) * 60 - now.second
    if secondsToWait < 5:
        secondsToWait += intervalMinutes * 60
    time.sleep(secondsToWait)
```

---

## BLACKOUT WINDOW

Blackout window = 5 menit sebelum settlement (00:00, 08:00, 16:00 UTC).

**Berlaku untuk: ENTRY saja. Exit tidak ter-affect.**

Alasan: blackout mencegah order entry yang tidak fill sebelum settlement — akibatnya
posisi terbuka tapi miss collect FR pertama. Exit tidak punya masalah ini.
Nilai nunggu 1 settlement saat exit hanya ~$0.03 per trade, tidak worth delay.

```python
def isBlackoutWindow() -> bool:
    """True jika dalam 5 menit sebelum settlement. Hanya block entry, tidak exit."""
    now = datetime.now(timezone.utc)
    for hour in SETTLEMENT_HOURS_UTC:
        settlement = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        diff = (settlement - now).total_seconds()
        if 0 < diff <= BLACKOUT_MINUTES * 60:
            return True
    return False
```

---

## REAL-TIME COST CALCULATION

Cost di live BUKAN flat tier — hitung dari orderbook setiap cycle:

```
fee_rt = 0.08%  (fixed, Binance taker fee × 2)

spread_spot    = (ask_spot - bid_spot) / mid_spot × 100
spread_futures = (ask_futures - bid_futures) / mid_futures × 100

slippage_spot    = estimate dari depth spot (scan asks sampai sizePerPair/2 terpenuhi)
slippage_futures = estimate dari depth futures (scan asks sampai sizePerPair/2 terpenuhi)
# sizePerPair di-fetch dari balance saat startup, bukan hardcode $300

basis = |markPrice - indexPrice| / indexPrice × 100

total_rt_cost = fee_rt
              + (spread_spot × 2)
              + (spread_futures × 2)
              + (slippage_spot × 2)
              + (slippage_futures × 2)
              + basis

net_expected = |FR_realtime| - total_rt_cost
```

Kalau `basis > 0.05%` → skip coin itu (dari Phase 0 rule).

---

## RISK GUARDS

```python
def isCostSpike(symbol: str, currentCost: float, costCache: dict) -> bool:
    """
    True kalau cost > 3x rolling average untuk coin ini.
    Pakai rolling average dari cost_cache, bukan hardcode dari Phase 0.
    Fallback ke DEFAULT_COST_TIER kalau belum ada history.
    """
    baseline = costCache.get(symbol, {}).get("rolling_avg", DEFAULT_COST_TIER)
    return currentCost > baseline * COST_SPIKE_MULTIPLIER

def isBroadMarketStress(costSamples: dict[str, float], costCache: dict) -> bool:
    """
    True kalau >50% coins punya cost > 2x rolling average mereka.
    """
    elevated = sum(
        1 for s, c in costSamples.items()
        if c > costCache.get(s, {}).get("rolling_avg", DEFAULT_COST_TIER) * 2
    )
    return elevated / len(costSamples) > BROAD_STRESS_THRESHOLD
```

---

## PARTIAL FILL PROTOCOL

```
Entry:
1. Place spot order + futures order bersamaan
2. Poll fill status setiap 5 detik
3. Kalau salah satu tidak fill dalam ORDER_TIMEOUT_SECONDS:
   a. Cancel KEDUA order
   b. Kalau satu sudah fill → close dengan market order immediately
   c. Log sebagai "partial_fill_failed", BUKAN trade
   d. Jangan retry di cycle yang sama

Exit:
1. Cancel SEMUA open orders untuk symbol (regular + algo)
2. Verify cancelled
3. Close posisi
4. Verify closed
5. Log konfirmasi
```

---

## ORPHAN ORDER CHECKER

Jalan setiap cycle setelah STEP 2:

```
1. GET /fapi/v1/positionRisk      → semua open positions
2. GET /fapi/v1/openOrders        → semua open regular futures orders
3. GET /api/v3/openOrders         → semua open spot orders
4. GET /fapi/v1/algo/orders/open  → semua open algo orders (SL/TP)
   ↑ TERPISAH dari regular orders — dua list berbeda, keduanya wajib di-check

Cross-check:
- Regular/algo order tanpa matching position → cancel immediate
- Position tanpa SL/TP → place emergency SL dengan MARK_PRICE, log WARNING
  Jangan hanya alert — place dulu, alert kemudian
```

---

## MANIPULATION HANDLING

Skenario: futures SL ter-trigger dari candle spike, tapi spot masih open (orphan spot).

**Primary defense — sudah built-in via MARK_PRICE SL:**
Mark Price tidak ikut spike sebesar Last Price → SL tidak trigger dari spike palsu.

**Secondary defense — di orphan checker:**
```
Bot detect: futures position closed tapi spot masih open
→ Immediately close spot dengan MARKET ORDER
→ Log sebagai manipulation_event: {timestamp, symbol, futures_close_price, spot_close_price}
→ Suspend coin dari entry selama 3 cycle
→ Jangan reopen posisi sampai situasi normal
```

**Monitoring:**
```
Hitung manipulation_event per coin per bulan
Kalau > 10% dari total trades coin itu → suspend lebih lama, review manual
Report di paper trading log akhir
```

---

## SL/TP — CRITICAL RULES

```python
# WAJIB via requests langsung, BUKAN ccxt
# POST /fapi/v1/algoOrder

params = {
    "symbol":       symbol,
    "side":         "BUY",           # untuk close short futures
    "positionSide": "SHORT",
    "quantity":     quantity,
    "orderType":    "STOP",
    "stopPrice":    stop_price,
    "workingType":  "MARK_PRICE",    # WAJIB — prevent fake spike trigger
}

# Response: {"algoId": 12345}  ← simpan ini
# Cancel: DELETE /fapi/v1/algoOrder dengan algoId, BUKAN orderId
# JANGAN pakai cancel_order() dari ccxt → wrong endpoint, fail silently
```

---

## TRADE LOG — FIELDS WAJIB

Setiap trade di-log ke file (append, jangan overwrite):

```python
{
    # Standard fields (sama dengan backtest)
    "trade_id":             str,   # f"{symbol}_{entry_time}"
    "symbol":               str,
    "side":                 str,   # "long_spot_short_futures" atau sebaliknya
    "entry_time":           str,   # ISO8601 UTC
    "exit_time":            str,
    "entry_fr":             float, # FR saat entry signal
    "exit_fr":              float,
    "hold_settlements":     int,
    "gross_pct":            float,
    "cost_rt_pct":          float, # actual cost, bukan flat tier
    "net_pct":              float,
    "net_dollar":           float,

    # Phase 4 tambahan — untuk validate backtest assumptions
    "fill_time_spot_ms":    int,   # berapa ms spot order fill
    "fill_time_futures_ms": int,
    "actual_fill_price_spot":    float,
    "actual_fill_price_futures": float,
    "slippage_spot_pct":    float, # (fill_price - mid_price) / mid_price * 100
    "slippage_futures_pct": float,
    "partial_fill_occurred": bool,
    "cost_tier":            str,   # "actual" atau "realtime"
}
```

---

## RESTART PROTOCOL

Setiap kali bot restart, sebelum cycle normal:

```
1. GET /fapi/v1/positionRisk → check semua open positions
2. GET /fapi/v1/algo/orders/open → verify SL/TP terpasang
3. Kalau ada position tanpa SL/TP → place emergency SL dulu
4. Reconcile trade log file dengan actual positions
5. Log downtime: {"start": ..., "end": ..., "duration_minutes": ..., "reason": ...}
```

---

## PAPER TRADING VALIDITY RULES

Valid kalau:
- Total downtime < 10% dari durasi (4 minggu = max 67 jam total downtime)
- Tidak ada unprotected position selama downtime > 1 settlement (8 jam)
- Trade log tidak hilang dan bisa di-reconstruct

Invalid (harus ulang dari nol) kalau:
- Ada posisi orphan tidak ter-close > 1 settlement
- Ada posisi tanpa SL/TP saat bot down
- Trade log corrupted/hilang

---

## VALIDATION METRICS — CHECK DI AKHIR PAPER TRADING

```
PASS kalau SEMUA:
  APY paper trading >= 13.2%          (absolute floor)
  APY paper trading >= 14%            (50% dari backtest 28%)
  Max drawdown < $50
  Fill rate >= 60%

FAIL kalau SALAH SATU:
  APY < 13.2%
  APY < 14%
  Max drawdown > $50
  Fill rate < 60%
```

---

## MONITORING METRICS (tidak blocking, tapi track per bulan)

- Top 10% trades sebagai % dari total net → alert kalau > 150%
- Manipulation events per coin → suspend kalau > 10% dari trades coin itu
- Avg fill time spot vs futures → indikasi liquidity
- Avg actual cost vs flat tier 0.12% → validasi cost assumption

---

## TEST YANG HARUS ADA SEBELUM BOT JALAN

### test_connectivity.py
Verify semua private endpoints accessible dari VPS:
```
□ GET  /api/v3/account
□ GET  /api/v3/openOrders
□ POST /api/v3/order (testnet — place dan cancel order kecil)
□ GET  /fapi/v2/balance
□ GET  /fapi/v1/positionRisk
□ POST /fapi/v1/order (testnet)
□ POST /fapi/v1/algoOrder (testnet)
□ DELETE /fapi/v1/algoOrder (testnet — pakai algoId)
□ GET  /fapi/v1/algo/orders/open
□ GET  /fapi/v1/depth
□ GET  /api/v3/depth
```

### test_executor.py
- Place spot + futures order bersamaan → verify keduanya fill
- Simulate timeout: cancel kalau salah satu tidak fill dalam 60s
- Place algo order → verify algoId tersimpan, bukan orderId
- Cancel algo order via algoId → verify cancelled
- Orphan detection: create orphan order, verify terdeteksi dan di-cancel

---

## YANG TIDAK BOLEH DILAKUKAN DI PHASE 4

- Jangan optimize entry/exit threshold berdasarkan paper trading results
- Jangan expand universe ke coins baru tanpa review
- Jangan ubah position sizing
- Jangan deploy ke mainnet sampai 4 minggu selesai dan pass semua metrics
- Jangan buka data 2026 untuk tuning apapun
- Jangan run multiple parameter variants simultaneously

---

## TRIAL REGISTRY

Setiap parameter change = satu trial. Max 5 trials sebelum review fundamental.
Update file `/root/quant-arb/phase0.md` section Trial Registry setiap ada perubahan.

```
Trial 0: baseline dari Phase 3 backtest (entry 0.05%, exit 0.02%)
Trial 1+: di-isi saat Phase 4 berjalan
```

Parameter yang boleh di-tune:
- min_profit_threshold (sekarang 0.01%)
- timeout limit order (sekarang 60 detik)

Parameter yang tidak boleh di-tune:
- entry_threshold, exit_threshold, max_pairs, buffer_ratio, universe
