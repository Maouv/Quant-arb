# PHASE 4: PAPER TRADING REQUIREMENTS
**Date:** 23 May 2026
**Status:** DRAFT — dikompilasi dari Phase 3 findings
**Depends on:** phase0.md, phase1.md, phase2.md, phase3-spec.md

---

## KONTEKS

Phase 4 adalah paper trading — bot jalan 24/7 dengan uang sungguhan di testnet Binance.
Tujuan bukan profit, tapi **validate asumsi yang tidak bisa divalidasi di backtest**:
- Actual fill rate per coin (backtest assume 100%)
- Actual cost per coin real-time (backtest pakai flat tier)
- Bot execution correctness (orphan orders, timing, race conditions)
- Apakah APY paper trading >= 50% dari backtest dan >= 13.2% absolute (rejection criteria Phase 0)

Minimum durasi: 4–6 minggu (dari Phase 1 Bagian 11).

---

## REPO DAN STRUKTUR

Phase 4 adalah repo TERPISAH dari quant-arb. Nama repo: `quant-arb-bot`.

Alasan pisah repo:
- Secrets (API key) tidak boleh satu repo dengan data analisis
- Mencegah accident deploy simulation code ke production
- Git history bersih — research dan production terpisah

Coding standards (sama dengan phase3_backtest):
- PEP8
- camelCase untuk variabel dan fungsi
- PascalCase untuk class
- Type hints wajib semua fungsi
- Docstring wajib semua fungsi dan class
- Max 30 baris per fungsi
- Tidak ada magic number — semua di config.py
- Tidak ada bare `except:` — semua exception explicit

Struktur repo Phase 4 (baru, terpisah):
```
quant-arb-bot/
├── config/
│   ├── config.py          # semua parameter, pisahkan testnet vs mainnet
│   └── secrets.env        # API keys — JANGAN di-commit ke git
├── bot/
│   ├── main.py            # entrypoint, clock-aligned cycle
│   ├── scanner.py         # scan FR semua coins, hitung net_expected
│   ├── executor.py        # place/cancel orders, verify fills
│   ├── position_manager.py # monitor posisi open, orphan check
│   └── risk_guard.py      # pre-entry checks, cost spike guard
├── data/
│   └── cost_cache.py      # cache real-time cost per coin
├── logs/                  # semua log disimpan di sini
└── tests/
    └── test_executor.py   # unit test untuk order logic
```

---

## NOTES DARI PHASE 3 — WAJIB DI-IMPLEMENT

### 1. Clock-Aligned Cycle
Bot harus align ke menit bulat yang habis dibagi 5, bukan simple interval.
Jika bot start jam x:27, tunggu sampai x:30 baru mulai cycle pertama.

```python
import time
from datetime import datetime, timezone

def waitForNextCycle(intervalMinutes: int = 5) -> None:
    """Wait until next clock-aligned cycle boundary."""
    now = datetime.now(timezone.utc)
    secondsToWait = (intervalMinutes - now.minute % intervalMinutes) * 60 - now.second
    if secondsToWait < 5:  # already near boundary, skip to next
        secondsToWait += intervalMinutes * 60
    time.sleep(secondsToWait)
```

### 2. Blackout Window Pre-Settlement
Jangan entry dalam 5 menit terakhir sebelum settlement.
Settlement times UTC: 00:00, 08:00, 16:00.

```python
SETTLEMENT_HOURS_UTC = [0, 8, 16]
BLACKOUT_MINUTES = 5

def isBlackoutWindow() -> bool:
    now = datetime.now(timezone.utc)
    for hour in SETTLEMENT_HOURS_UTC:
        settlement = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        diff = (settlement - now).total_seconds()
        if 0 < diff <= BLACKOUT_MINUTES * 60:
            return True
    return False
```

### 3. Min Profit Threshold (dari Phase 3 finding)
Backtest tidak punya pre-entry filter — semua trades dengan FR >= 0.05% masuk.
Akibatnya 70% trades (hold <= 3 hari) aggregate rugi $271.

Di live, tambahkan filter sebelum entry:
```python
MIN_PROFIT_THRESHOLD = 0.01  # % buffer di atas break-even

net_expected = fr_realtime - cost_rt_realtime
if net_expected < MIN_PROFIT_THRESHOLD:
    skip  # jangan entry
```

Ini akan mengurangi jumlah trades tapi meningkatkan win rate dan avg net per trade.
Effect-nya perlu di-measure di paper trading dan compare ke backtest.

### 4. Cost Spike Guard (dari execution realism audit)
Kalau real-time cost > 3x normal tier untuk coin tersebut, jangan entry baru.
Untuk posisi yang sudah open: tidak force close, tapi log sebagai "elevated cost warning".

```python
COST_SPIKE_MULTIPLIER = 3.0

def isCostSpike(symbol: str, currentCost: float) -> bool:
    baseCost = getBaseCostForSymbol(symbol)  # dari ACTUAL_COSTS atau tier
    return currentCost > baseCost * COST_SPIKE_MULTIPLIER
```

### 5. LUNA-Level Safeguard (dari stress test finding)
Strategi tidak survive kalau spread melebar > 2x selama crash. Di live, stop new entries
kalau detected broad market cost spike (majority coins tiba-tiba mahal).

```python
def isBroadMarketStress(costSamples: dict[str, float]) -> bool:
    """True kalau >50% coins punya cost > 2x normal."""
    elevated = sum(1 for s, c in costSamples.items() if c > getBaseCostForSymbol(s) * 2)
    return elevated / len(costSamples) > 0.5
```

---

## NOTES DARI PHASE 0/1 — CARRY FORWARD

### 6. Orphan Order Checker (dari Phase 0 Bagian 7)
Jalan setiap cycle. Check regular orders DAN algo orders (dua endpoint berbeda).

```
1. Get semua open positions
2. Get semua open regular orders (GET /api/v3/openOrders)
3. Get semua open algo orders (GET /fapi/v1/algo/orders/open) — ENDPOINT TERPISAH
4. Order tanpa matching position → cancel immediate
5. Position tanpa SL/TP → alert manual intervention
```

### 7. Partial Fill Protocol (dari Phase 0 Bagian 3)
Kalau spot fill tapi futures tidak fill dalam 60 detik (atau sebaliknya):
- Cancel semua order
- Close leg yang sudah fill dengan market order immediately
- Log sebagai failed attempt, bukan trade
- Jangan retry di cycle yang sama

### 8. SL/TP — Algo Order (dari Phase 0 Bagian 7)
- Pakai `workingType = "MARK_PRICE"` bukan `CONTRACT_PRICE`
- Cancel pakai `algoId`, BUKAN `orderId`
- Jangan pakai `cancel_order()` dari ccxt untuk algo orders

### 9. ccxt Version Lock (dari Phase 0 Bagian 7)
```
ccxt == 4.2.86  # LOCKED — versi baru block testnet futures API
```

---

## VALIDATION METRICS (dari Phase 0 Rejection Criteria)

Paper trading dinyatakan **PASS** kalau:
- APY paper trading >= 50% dari backtest APY (backtest mid: ~28% → floor 14%)
- APY paper trading >= 13.2% absolute
- Max drawdown < $50 dalam periode paper trading

Paper trading dinyatakan **FAIL** kalau salah satu:
- APY < 13.2%
- APY < 50% dari backtest
- Max drawdown > $50
- Fill rate realisasi < 60% (berarti execution fundamentally broken)

---

## METRICS YANG HARUS DI-TRACK (yang tidak bisa ditrack di backtest)

Per trade, log tambahan untuk Phase 4:
- `fill_time_spot_ms` — berapa ms spot order fill
- `fill_time_futures_ms` — berapa ms futures order fill
- `actual_fill_price_spot` — harga actual fill vs mid price
- `actual_fill_price_futures`
- `actual_cost_rt_pct` — cost actual (bukan flat tier)
- `slippage_pct` — selisih fill price vs mid price
- `partial_fill_occurred` — boolean

Ini data yang akan dipakai untuk update cost model di Phase 5.

---

## INTERRUPT HANDLING

### Restart Protocol
Setiap kali bot restart (apapun alasannya), langkah pertama sebelum cycle normal:
```
1. Check semua open positions di Binance
2. Verify semua positions punya SL/TP terpasang
3. Kalau ada position tanpa SL/TP → place emergency SL dulu, baru lanjut
4. Reconcile trade log file dengan actual positions
5. Log downtime: start_time, end_time, duration, alasan
```

### Jenis Interrupt

Tidak invalidate paper trading (fix dan lanjut):
- Bot crash karena bug code
- VPS reboot
- API timeout sementara
- Syarat: semua posisi masih terlindungi SL/TP selama downtime

Invalidate paper trading (harus ulang dari nol):
- Ada posisi orphan tidak ter-close selama downtime > 1 settlement (8 jam)
- Ada posisi tanpa SL/TP selama bot down
- Trade log hilang dan tidak bisa di-reconstruct

### Validity Rules
Paper trading dinyatakan valid hanya kalau:
- Total downtime < 10% dari durasi (4 minggu = max 67 jam)
- Tidak ada unprotected position selama downtime > 1 settlement

---

## YANG TIDAK BOLEH DI-IMPLEMENT DI PHASE 4

- Jangan optimize parameter (entry/exit threshold) berdasarkan paper trading results
- Jangan expand universe ke coins baru tanpa review
- Jangan ubah position sizing
- Jangan deploy ke mainnet sampai paper trading >= 4 minggu dan pass rejection criteria

---

## YANG BELUM DI-TEST DI PHASE 0 — HARUS DI-TEST SEBELUM BOT JALAN

Dari phase0-api-docs.md, private endpoints belum pernah di-test dari VPS:
- `GET /api/v3/account` — spot balance
- `GET /fapi/v2/account` — futures balance
- `POST /api/v3/order` — place spot order
- `POST /fapi/v1/order` — place futures order
- `POST /fapi/v1/algoOrder` — place SL/TP
- `GET /fapi/v1/depth` — order book depth (untuk slippage estimate)
- `GET /api/v3/depth` — order book depth spot

**Wajib test semua endpoint ini di testnet sebelum paper trading dimulai.**
Buat script `tests/test_connectivity.py` yang verify semua endpoint bisa dipanggil
dan response format sesuai ekspektasi.

---

## DATA TEST SET — DOWNLOAD SAAT PHASE 4 DIMULAI

Dari Phase 0 data split protocol:
- Test set: 2026-01-01 sampai sekarang
- Belum didownload — download saat Phase 4 dimulai
- Dipakai untuk: forward validation setelah paper trading selesai
- Tidak boleh dipakai untuk tuning apapun

---

## TRIAL REGISTRY — LANJUTKAN DARI PHASE 0

Phase 0 menetapkan max 5 trials sebelum review fundamental hypothesis.
Trial 0 = baseline dari Phase 3 backtest.

Setiap perubahan parameter di Phase 4 = satu trial baru.
Parameter yang boleh di-tune: entry threshold, exit threshold, min_profit_threshold, timeout limit order.
Parameter yang tidak boleh di-tune: universe, cost model methodology, position sizing, buffer ratio.

Update trial registry di phase0.md setiap ada perubahan.

---

## MANIPULATION EVENT MONITORING

Dari Phase 0: kalau futures SL ter-trigger tanpa spot ikut → log sebagai manipulation_event.
Kalau > 10% dari total trades satu coin = manipulation events → suspend coin dari universe sementara.
Track per coin per bulan selama paper trading.

---

## FINDINGS DARI VALIDATION 2025 — CARRY FORWARD KE PHASE 4

### Threshold tidak perlu diubah
Entry 0.05% menghasilkan net tertinggi ($834 training, $497 validation).
Menaikkan threshold mengurangi net dollar. Biarkan di 0.05%.

### Payoff strategi bersifat option-like — ini normal
70% trades loss kecil, 30% win besar. Win/loss ratio ~13:1.
Top 10% trades menghasilkan 100-115% dari total net.
Ini karakteristik struktural, bukan bug. Monitor per bulan di Phase 4 — alert kalau > 150%.

### Validation 2025 hasil (semua PASS)
- Net $497 vs floor $278
- Max DD $4.19 vs limit $50
- Win rate 37.7% vs floor 30%
- Top 10% concentration 103.9% vs revised threshold 150%

### Yang belum terbukti — harus divalidasi Phase 4
- Fill rate actual (backtest assume 100%)
- Cost actual per coin real-time (backtest pakai flat tier)
- Apakah edge persist di 2026

---

## STATUS

```
DRAFT — 23 May 2026
Dikompilasi dari Phase 3 session notes
Perlu review sebelum Phase 4 dimulai
```
