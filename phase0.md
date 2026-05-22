# PHASE 0: FOUNDATION DOCUMENT
## Funding Rate Arbitrage Strategy
**Date:** 19 May 2026  
**Status:** DRAFT v3.3 — pending review  
**Author:** Maou  
**Repo:** github.com/Maouv/quant-arb  
**num_trials:** 0  

---

## BAGIAN 1 — ECONOMIC HYPOTHESIS

### Pernyataan Hipotesis
Ketika funding rate perpetual futures melebihi threshold tertentu (positif atau negatif), terjadi kondisi overleveraged yang menciptakan opportunity untuk harvest yield secara delta neutral — tanpa mengambil directional bet pada harga.

### Mekanisme Ekonomi

**Mekanisme 1 — Basis Divergence:**  
Ketika banyak trader overleveraged di satu sisi (long atau short), harga perp menjadi jauh dari harga spot. Gap ini secara mechanical akan dikonvergensikan oleh arbitrageur. Ini bukan prediksi harga — ini mechanical process yang terjadi regardless of market direction.

**Mekanisme 2 — Yield Collection:**  
Trader yang overleveraged membayar funding cost setiap 8 jam kepada sisi yang berlawanan. Posisi delta neutral (long spot + short futures, atau sebaliknya) collect payment ini tanpa exposure ke price direction.

### Siapa Di Sisi Lain
FOMO dan momentum traders yang masuk late dan tidak menghitung funding cost ke dalam expected return mereka. Mereka tidak irrational secara sadar — mereka tidak aware of the carry cost relatif terhadap expected return mereka.

### Posisi Yang Diambil
**Delta neutral:**
```
Funding rate positif (banyak long):
→ Short futures + Long spot
→ Terima pembayaran dari long side

Funding rate negatif (banyak short):
→ Long futures + Short spot
→ Terima pembayaran dari short side
```
Tidak ada directional bet. P&L dari price movement seharusnya wash.

### Hipotesis SALAH Jika
1. Funding rate flip sebelum posisi di-close → kita bayar, bukan terima
2. Basis divergence tidak konvergen dalam expected timeframe
3. Market sangat volatile → cost actual jauh melebihi estimasi
4. Net yield setelah semua cost secara konsisten negatif di majority universe
5. Exchange freeze atau maintenance → tidak bisa rebalance posisi
6. Liquidity crisis → spread melebar drastis saat exit
7. Funding rate manipulation oleh whale → trap arb traders
8. Coin di-delist → forced settlement dengan harga buruk
9. Partial fill pada entry → naked exposure tanpa hedge
10. Delta tidak benar-benar neutral → price movement menciptakan P&L signifikan
11. Past FR tidak predictive of next FR
    → Entry berdasarkan lastFundingRate tapi
      actual next FR < threshold
    → Ini yang sedang di-verify Opus (#4)
12. Fill rate terlalu rendah (<60%)
    → Effective trades/year jauh di bawah theoretical
    → Yield estimate tidak valid

### Threshold Entry/Exit
Akan di-derive dari data di Phase 1 berdasarkan cost model per coin.  
Prior ekonomi: entry threshold minimum > total round trip cost per settlement period.  
**Angka exact tidak di-hardcode di Phase 0 — harus dari data.**

---

## BAGIAN 2 — UNIVERSE DEFINITION

### Tujuan Universe
Universe bukan guaranteed entry — universe adalah **safety filter.**  
Bot tetap memilih coin berdasarkan FR real-time dari pool ini.  
Idealnya bot scan semua pairs, tapi universe diperlukan untuk:
- Pre-verify liquidity yang adequate
- Exclude pairs yang manipulated atau mau delist
- Prevent rate limit API dari scan 300+ pairs setiap cycle

### Inclusion Criteria
- Listed di Binance dengan **KEDUANYA**: spot pair USDT dan perpetual futures USDT-margined
- Minimum average daily volume: **$10 juta** (spot)
- Minimum market cap: **$100 juta**
- Minimum funding rate history: **12 bulan**
- Funding interval: **8 jam only** (konsistensi data)
- Bukan stablecoin atau wrapped token

### Universe — 11 Coin (Safety Pool)
```
ETHUSDT   XRPUSDT   DOGEUSDT  SUIUSDT   ADAUSDT
LINKUSDT  UNIUSDT   ZECUSDT   INJUSDT   NEARUSDT
AAVEUSDT
```
Entry dari pool ini ditentukan oleh bot berdasarkan:
```
net_expected = FR_realtime - total_rt_cost_realtime
Hanya masuk posisi kalau net_expected > min_profit_threshold
```

### Cost Model Per Coin (Sampled 5x, 19 May 2026)
Angka di bawah adalah combined spot + futures (dua layer):

| Symbol   | Spread RT% | Slippage RT% | Total RT% | Note |
|----------|------------|--------------|-----------|------|
| ETHUSDT  | 0.0010%    | 0.0004%      | 0.0814%   | Low cost |
| XRPUSDT  | 0.0146%    | 0.0072%      | 0.1018%   | Low cost |
| DOGEUSDT | 0.0192%    | 0.0096%      | 0.1088%   | Low cost |
| SUIUSDT  | 0.0188%    | 0.0132%      | 0.1119%   | Low cost |
| LINKUSDT | 0.0208%    | 0.0104%      | 0.1113%   | Low cost |
| ZECUSDT  | 0.0036%    | 0.0046%      | 0.0882%   | Low cost |
| AAVEUSDT | 0.0226%    | 0.0248%      | 0.1275%   | Low cost |
| ADAUSDT  | 0.0802%    | 0.0400%      | 0.2002%   | High cost — butuh FR spike besar |
| INJUSDT  | 0.0400%    | 0.0360%      | 0.1562%   | Medium cost |
| UNIUSDT  | 0.0572%    | 0.0400%      | 0.1773%   | Medium cost |
| NEARUSDT | 0.1236%    | 0.0618%      | 0.2655%   | Highest cost — jarang viable |

Note: Spread RT% = spread_spot×2 + spread_futures×2 (estimate sama karena single exchange)  
Slippage RT% = slippage_spot×2 + slippage_futures×2  
Total RT% = fee(0.08%) + Spread RT% + Slippage RT%

**Cost bersifat dinamis** — berubah berdasarkan waktu, volatility, liquidity.  
Tabel ini adalah baseline reference, bukan angka fixed.  
**Harus di-resample di Phase 1 dengan lebih banyak data point.**

### Excluded Permanent — Dengan Alasan
| Coin | Alasan |
|------|--------|
| SOL  | Mean FR negatif, std ekstrem (0.1097%), min -2.0% — kemungkinan data anomali. Verify di Phase 1: kalau genuine event → tetap excluded, kalau data error → reconsider |
| ONDO | Funding interval 4 jam — tidak konsisten dengan universe |
| TAO  | Funding interval 4 jam — tidak konsisten dengan universe |
| HYPE | Tidak ada spot pair di Binance |

### NEAR — Special Case
```
NEAR ada di universe (eligible) tapi cost tertinggi (0.2655%)
→ Di backtest: EXCLUDED (cost historis struktural > yield historis)
→ Di testnet/live: ELIGIBLE tapi hampir selalu gagal dynamic cost filter
   Hanya masuk posisi kalau ada FR spike besar yang nutup cost 0.2655%+
```

### Minimum Notional
Tidak di-hardcode. Di-fetch dari API setiap bot startup:
```
GET /fapi/v1/exchangeInfo
→ Ambil filter MIN_NOTIONAL per symbol
→ Validate bahwa position size kita > min notional
→ Kalau tidak → skip coin itu
```

### Universe Locked
Tidak ada penambahan atau pengurangan coin setelah Phase 1 dimulai, kecuali:
- Forced delisting oleh Binance
- Data quality issue yang ditemukan di Phase 1

### Roadmap Expansion
```
Phase 1-5: Single exchange Binance (spot + futures)
Post Phase 5: Cross exchange expansion jika proven profitable
              dan yield terlalu rendah untuk scale
```

---

## BAGIAN 3 — COST MODEL

### Komponen Biaya
```
1. Fee (exact, tidak berubah):
   Taker fee: 0.04% per side = 0.08% round trip
   Sumber: Binance official fee schedule

2. Spread — dua layer (dinamis, fetch real-time):

   Layer 1: Spread per sisi (spot dan futures terpisah)
   spread_spot    = (ask_spot - bid_spot) / mid_spot × 100
   spread_futures = (ask_futures - bid_futures) / mid_futures × 100
   Di-fetch dari bookTicker spot DAN futures setiap cycle

   Layer 2: Basis divergence (spot vs futures price gap)
   basis = |markPrice - indexPrice| / indexPrice × 100
   Di-fetch dari /fapi/v1/premiumIndex
   Normal: <0.01% | Volatile: bisa 0.1-0.5%
   Kalau basis > threshold → JANGAN entry, tunggu konvergen

3. Slippage — dua layer (dinamis, estimate dari order book):
   slippage_spot    = estimate dari depth spot order book
   slippage_futures = estimate dari depth futures order book
   Keduanya dihitung untuk size $500

   Formula:
   Scan asks dari best ask, accumulate sampai $500 terpenuhi
   worst_fill_price = harga ask terakhir yang dipakai
   slippage = (worst_fill_price - mid_price) / mid_price × 100

   Pseudocode:
   cumulative = 0
   worst_price = best_ask
   for price, qty in order_book['asks']:
       cumulative += price * qty
       worst_price = price
       if cumulative >= position_size:
           break
   slippage = (worst_price - mid_price) / mid_price * 100

Total RT cost = fee_rt
              + (spread_spot × 2)
              + (spread_futures × 2)
              + (slippage_spot × 2)
              + (slippage_futures × 2)
              + basis_divergence
```

### Basis Divergence Threshold
```
Di-fetch: GET /fapi/v1/premiumIndex → markPrice vs indexPrice

IF basis > 0.05%:
   → Jangan entry — cost terlalu tinggi dari basis saja
   → Tunggu basis konvergen
   → Log sebagai "high basis — skip"

Threshold 0.05% akan di-validate di Phase 1
```

### Dynamic Cost Filter (Pre-Entry Check)
Dijalankan setiap cycle sebelum entry:
```
net_expected = FR_realtime - total_rt_cost_realtime

IF net_expected < min_profit_threshold → SKIP
IF net_expected >= min_profit_threshold → KANDIDAT ENTRY

min_profit_threshold = di-derive dari Phase 1
Prior: ~0.02% per settlement sebagai buffer minimum
```

Contoh konkret:
```
NEARUSDT saat normal:
  FR = 0.06%, cost = 0.27% → net = -0.21% → SKIP

NEARUSDT saat spike:
  FR = 0.35%, cost = 0.27% → net = +0.08% → KANDIDAT

ETHUSDT saat normal:
  FR = 0.04%, cost = 0.08% → net = -0.04% → SKIP

ETHUSDT saat moderate FR:
  FR = 0.12%, cost = 0.08% → net = +0.04% → KANDIDAT
```

### Execution Rules
```
Normal entry/exit:
→ Limit order di mid price
   Mid price = (best_bid + best_ask) / 2
→ Timeout: 60 detik
→ Kalau tidak fill: cancel, reassess cycle berikutnya

Emergency exit (funding flip imminent):
→ Market order — execution lebih penting dari cost
→ Trigger: predicted FR mendekati flip threshold
```

### Partial Fill Protocol
```
Entry:
1. Kirim spot + futures order bersamaan
2. Monitor fill setiap 5 detik
3. Kalau salah satu tidak fill dalam 60 detik:
   → Cancel KEDUANYA
   → Log sebagai failed attempt
   → Coba lagi cycle berikutnya
4. Kalau satu fill, satu timeout:
   → IMMEDIATELY close yang sudah fill (market order)
   → Tidak dihitung sebagai trade

Exit:
1. Cancel SEMUA open orders symbol (regular + algo)
2. Verify cancelled
3. Close posisi
4. Verify closed
5. Log confirmation
```

### Orphan Order Checker
Jalan setiap cycle:
```
1. Get semua open positions
2. Get semua open regular orders
3. Get semua open algo orders — endpoint TERPISAH
4. Order tanpa matching position → cancel immediate
5. Position tanpa SL/TP → place emergency atau alert
```

### USDT Basis Risk
```
USDT basis risk:
- Spot dan futures margin keduanya dalam USDT
- Kalau USDT depeg → basis bisa shift
- Edge case tapi real risk
- Acknowledged, tidak di-hedge untuk sekarang
```

---

## BAGIAN 4 — DATA SPLIT PROTOCOL

### Data Yang Tersedia
```
Funding rate + OHLCV: 2022-01 sampai 2025-12 (downloaded)
Forward data:         2026-01 sampai sekarang (belum didownload)
```

### Split Final
```
TRAIN:      2022-01 → 2024-12
            Dipakai di: Phase 1, 2, 3
            Untuk: viability analysis, math framework, backtest

VALIDATION: 2025-01 → 2025-12
            Dipakai di: Phase 3 stress test
            Dibuka: setelah backtest di train selesai
            Dibuka: SATU KALI saja

TEST:       2026-01-01 sampai sekarang dan seterusnya
            Di-download saat Phase 4 dimulai, bukan sekarang
            Tidak ada data 2026 yang didownload sampai Phase 4
```

### NEAR Di Backtest
```
NEAR di-exclude dari backtest (training + validation set)
Alasan: cost historis struktural lebih tinggi dari yield historis
Ini keputusan pre-hoc — tidak boleh diubah setelah melihat hasil
```

### Rules
```
- Validation set dibuka SATU KALI
- Test set tidak didownload sampai Phase 4
- Tidak ada parameter tuning setelah validation dibuka
- Setiap akses ke validation/test didokumentasikan
  dengan tanggal dan alasan
```

---

## BAGIAN 5 — EXPERIMENT GOVERNANCE

### Capital
```
Testnet:           $5,000 (Binance testnet)
Real (Phase 5+):   TBD setelah paper trading proven
Buffer:            40% tidak di-deploy (margin fluctuation)
effective_balance = total_balance × 0.60
```

### Position Sizing
```
Method: Equal weight
Definisi: Setiap pair yang masuk posisi mendapat
          alokasi kapital yang SAMA RATA
          Bukan weighted by FR magnitude
          Bukan weighted by coin market cap

max_pairs: 6
size_per_pair = effective_balance / max_pairs

Contoh:
Total balance: $5,000
effective_balance: $5,000 × 0.60 = $3,000
size_per_pair: $3,000 / 6 = $500
  → $250 di spot
  → $250 di futures (margin)

Kalau hanya 4 pair yang masuk threshold:
  Tetap $500 per pair
  Sisa $1,000 IDLE — tidak di-deploy ke pair lain
  Tidak ada re-allocation, tidak ada exception
  Idle capital adalah buffer, bukan waste
```

### Minimum Notional
```
Di-fetch dari /fapi/v1/exchangeInfo setiap bot startup/restart
Disimpan di memory selama bot running
Tidak di-fetch ulang setiap cycle (tidak perlu)

Validation sebelum entry:
IF position_size < min_notional → skip coin itu
IF position_size >= min_notional → eligible
```

### Coin Selection Di Bot
```
Bukan whitelist-driven (bukan "ETH selalu masuk")
Tapi FR-driven:
  Scan semua coin di universe setiap cycle
  Hitung net_expected per coin
  Sort by net_expected tertinggi
  Pilih top N sesuai slot available
```

### Experiment Rules
```
num_trials:  mulai dari 0
Max trials:  5 sebelum review fundamental hypothesis
Satu trial = setiap perubahan parameter threshold

Parameter BOLEH di-tune:
→ Entry threshold FR
→ Exit threshold FR
→ min_profit_threshold
→ Timeout limit order

Parameter TIDAK BOLEH di-tune:
→ Universe (locked)
→ Cost model methodology
→ Position sizing method (equal weight)
→ Data split dates
→ NEAR exclusion di backtest
```

### Trial Registry
```
Trial | Date | Parameter Change | Train Result | Val Result | Notes
------|------|-----------------|--------------|------------|------
0     |      | baseline        |              |            |
```

---

## BAGIAN 6 — REJECTION CRITERIA

### Strategy Tidak Work Jika
```
1. Net yield negatif di >50% coin universe
   setelah cost di training data

2. Funding flip frequency > 30% dari holding periods

3. Stress test — Opsi C (Yield accurate + Cost scenario):

   YIELD STRESS (dari data historis FR — accurate):
   Filter FR data di tiga periode crash:
   - LUNA crash:    2022-05-01 sampai 2022-05-31
   - FTX collapse:  2022-11-01 sampai 2022-11-30
   - BTC crash:     2024-08-01 sampai 2024-08-31
   
   Hitung per periode:
   → Berapa kali funding flip terjadi?
   → Berapa average FR vs normal period?
   → Berapa net yield dengan cost normal?

   COST STRESS (scenario — bukan data real):
   Karena historical orderbook tidak tersedia,
   run tiga scenario cost multiplier:
   
   for multiplier in [3x, 5x, 10x]:
       cost_stressed = normal_cost * multiplier
       net_yield = FR_historical - cost_stressed
       hitung drawdown dan survival rate
   
   Output yang dicari:
   "Strategy break even kalau spread tidak lebih
    dari Nx normal saat crash"
   
   Rejection threshold:
   Kalau strategy tidak survive scenario 3x →
   terlalu fragile, reject
   Kalau survive 3x tapi tidak 5x →
   acceptable dengan caveat
   Kalau survive 10x → sangat robust

4. Paper trading annualized yield % < 50% dari backtest
   annualized yield %
   Contoh: backtest 8% APY → paper trading minimal 4% APY
   Kalau di bawah ini → execution jauh lebih buruk dari simulasi

5. Setelah 5 trials tidak ada improvement meaningful

6. Manipulation events (futures SL trigger tanpa spot ikut)
   > 10% dari total trades di satu coin
   → Coin itu di-suspend dari universe sementara
   → Review apakah structural atau one-off
```

### Kalau Rejected — Review Urutan
```
A. Cost terlalu tinggi → evaluate coin lain di universe
B. FR jarang melewati threshold → evaluate threshold
C. Execution buruk → evaluate order type / timing
D. Yield struktural terlalu rendah → evaluate cross exchange
E. Fundamental strategy tidak work → pivot
```

---

## BAGIAN 7 — TECHNICAL CONSTRAINTS

### Library dan Version
```
ccxt:     4.2.86 (LOCKED — jangan upgrade)
          Versi baru block testnet futures API
Algo API: Via requests langsung, BUKAN ccxt
          ccxt tidak support /fapi/v1/algoOrder
```

### Dua Instance ccxt (Wajib)
```python
# Spot — untuk long/short spot
spot_exchange = ccxt.binance({
    "apiKey": ...,
    "secret": ...,
    "options": {"defaultType": "spot"},
    "recvWindow": 60000,
    "adjustForTimeDifference": True,
})

# Futures — untuk short/long perp
futures_exchange = ccxt.binanceusdm({
    "apiKey": ...,
    "secret": ...,
    "options": {"defaultType": "future"},
    "recvWindow": 60000,
    "adjustForTimeDifference": True,
})
```
`recvWindow` dan `adjustForTimeDifference` wajib —
clock VPS sering drift dari Binance server time.

### API Endpoints Reference
```
SPOT (api.binance.com):
GET    /api/v3/account          → saldo spot
POST   /api/v3/order            → place spot order
DELETE /api/v3/order            → cancel spot order
GET    /api/v3/openOrders       → list open spot orders

FUTURES (fapi.binance.com):
GET    /fapi/v2/account         → saldo futures
GET    /fapi/v2/balance         → balance per asset
POST   /fapi/v1/order           → place futures order
DELETE /fapi/v1/order           → cancel futures order
GET    /fapi/v1/openOrders      → list open futures orders
GET    /fapi/v1/positionRisk    → list open positions
GET    /fapi/v1/premiumIndex    → predicted FR (real-time)
GET    /fapi/v1/fundingRate     → historical FR
GET    /fapi/v1/ticker/bookTicker → real-time bid/ask
GET    /fapi/v1/exchangeInfo    → min notional per symbol

ALGO ORDER (futures, via requests bukan ccxt):
POST   /fapi/v1/algoOrder           → place SL/TP
DELETE /fapi/v1/algoOrder           → cancel SL/TP
GET    /fapi/v1/algo/orders/open    → list open algo orders
```

### SL/TP — Algo Order (Kritis)
```
Returns key: 'algoId' — BUKAN 'orderId'
Cancel: pakai algoId, BUKAN orderId
JANGAN pakai cancel_order() → wrong endpoint, fail silently

Regular orders dan algo orders = DUA LIST TERPISAH
Keduanya harus di-check saat orphan detection

WAJIB: workingType = "MARK_PRICE" bukan "CONTRACT_PRICE"
Alasan: Last Price bisa di-spike oleh manipulator
        Mark Price = weighted average spot + futures
        Jauh lebih susah di-manipulate
        SL tidak akan trigger dari candle spike palsu
```

### Market Manipulation Handling
Skenario: futures SL ke-trigger dari candle spike, spot masih open:
```
Primary defense — Mark Price SL:
→ Pasang SL dengan workingType: MARK_PRICE
→ Candle spike di Last Price tidak trigger SL
→ Mark Price tidak ikut spike sebesar Last Price

Secondary defense — Orphan detection:
→ Bot detect: futures closed tapi spot masih open
→ Immediately close spot dengan market order
→ Log sebagai "manipulation_event" dengan timestamp + coin
→ Suspend coin dari entry selama N cycle (default: 3 cycle)
→ Jangan reopen posisi sampai situasi normal

Monitoring:
→ Hitung manipulation_event per coin per bulan
→ Kalau > 10% dari total trades → suspend lebih lama
→ Report di Phase 4 paper trading log
```

### Bot Pipeline — Setiap Cycle (5 Menit)
```
STEP 1 — FETCH DATA
→ Real-time cost per coin:
  - Spread spot dari Binance spot bookTicker
  - Spread futures dari Binance futures bookTicker
  - Slippage estimate dari order book depth (spot + futures)
  - Basis divergence dari /fapi/v1/premiumIndex
→ Predicted FR semua coin universe
→ Posisi yang sedang open
→ Min notional per coin (saat startup saja, bukan tiap cycle)

STEP 2 — MONITOR POSISI EXISTING
→ Untuk setiap posisi open:
  Predicted FR masih di atas exit threshold?
  Orphan orders check (regular + algo)
  Kalau FR mau flip → emergency exit (market order)

STEP 3 — CARI OPPORTUNITY BARU
→ Untuk setiap coin tanpa posisi open:
  Kalau basis > 0.05% → skip, tunggu konvergen
  net_expected = FR_realtime - total_rt_cost_realtime
                 (total_rt_cost include basis divergence)
  Kalau net_expected > min_profit_threshold → kandidat

STEP 4 — RANK DAN FILTER
→ Sort kandidat by net_expected (tertinggi dulu)
→ Cek slot available (max 3 pairs)
→ Kalau ada slot → execute entry

STEP 5 — EXECUTE ENTRY
→ Place spot + futures order bersamaan (limit, mid price)
→ Verify fill dalam 60 detik
→ Place SL/TP via algo order API
→ Verify SL/TP terplace
→ Log semua

STEP 6 — ORPHAN CHECK
→ Order tanpa matching position → cancel
→ Position tanpa SL/TP → alert manual intervention
```

### Known Error Codes
| Code  | Cause | Fix |
|-------|-------|-----|
| -4137 | Stop price already triggered | Skip, log warning |
| -4120 | Pakai /fapi/v1/order untuk algo | Pakai place_algo_order() |

### Position Symbol — Verified
```
ccxt calls:  'BTC/USDT:USDT' (unified format)
API raw:     pos['info']['symbol'] → 'BTCUSDT'
```

### Order Status
```
if order_status in ("filled", "closed"):
    # keduanya = executed
```

### Live vs Testnet
```
Dikontrol via config: system.use_testnet
confirm_mainnet harus True sebelum live
Setelah ganti config → RESTART bot
```

### Phase Mulai Nulis Code
```
Phase 0-2: Dokumen + analysis scripts saja
Phase 3:   Mulai tulis struktur code production
           (folder structure, config, logging, style)
Phase 4:   Bot production jalan 24/7
Phase 5:   Same code Phase 4, ganti config → mainnet
```

### Rate Limiting Binance
```
Rate limiting Binance:
- Spot: 1200 request weight/menit
- Futures: 2400 request weight/menit
- 108 coins × multiple calls = ratusan requests/cycle
- Solusi: pakai batch endpoints kalau tersedia
  atau kurangi scan frequency
- Perlu di-validate sebelum Phase 3
```

### Settlement Timing
```
Settlement timing:
- Harus in position SEBELUM settlement untuk collect FR
- 00:00, 08:00, 16:00 UTC
- Entry timing optimal belum di-analyze (Phase 1 todo)
```

---

## STATUS DOKUMEN

```
DRAFT v3.4 — 22 May 2026
Pending review oleh Maou

Changes dari v3.3:
- Position sizing: max pairs 6, size dari saldo actual
  effective_balance = total_balance × 0.60
  size_per_pair = effective_balance / max_pairs
- Hipotesis SALAH: tambah poin 11 (Past FR tidak predictive)
  dan poin 12 (Fill rate terlalu rendah)
- Cost model: tambah USDT basis risk (acknowledged, tidak di-hedge)
- Technical constraints: tambah rate limiting Binance dan settlement timing

Next step setelah approved:
→ Mulai Phase 1: Viability Analysis
```

