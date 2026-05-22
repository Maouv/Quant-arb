# API REFERENCE DOCUMENT
## Funding Rate Arbitrage Bot
**Date:** 19 May 2026  
**Status:** VERIFIED  
**Repo:** github.com/Maouv/quant-arb  

---

## VERIFICATION STATUS

Semua public endpoints di-test dari VPS, 19 May 2026:
```
✅ Futures ping
✅ Predicted FR
✅ Historical FR
✅ Futures bookTicker
✅ Exchange info
✅ Spot ping
✅ Spot bookTicker
```
Private endpoints belum di-test (butuh API key).

---

## BASE URLS

```python
BASE_SPOT    = "https://api.binance.com"
BASE_FUTURES = "https://fapi.binance.com"
BASE_ALGO    = "https://fapi.binance.com"  # sama, endpoint berbeda
BASE_TESTNET_FUTURES = "https://testnet.binancefuture.com"
BASE_TESTNET_SPOT    = "https://testnet.binance.vision"
```

---

## PUBLIC ENDPOINTS (Tidak butuh API key)

### Futures — System
```
GET /fapi/v1/ping
→ Health check futures API
→ Response: {}
→ Verified: ✅
```

### Futures — Market Data
```
GET /fapi/v1/premiumIndex
→ Predicted funding rate + mark price + index price
→ Params: symbol (optional, kalau kosong return semua)
→ Key fields:
   markPrice       → harga mark (untuk SL/TP reference)
   indexPrice      → harga index spot
   lastFundingRate → FR terakhir yang settled
   nextFundingTime → waktu settlement berikutnya (ms)
   interestRate    → interest rate component
→ Verified: ✅

Contoh query satu coin:
GET /fapi/v1/premiumIndex?symbol=ETHUSDT

Contoh query semua coin (untuk scan universe):
GET /fapi/v1/premiumIndex
```

```
GET /fapi/v1/fundingRate
→ Historical funding rate
→ Params: symbol, startTime, endTime, limit (max 1000)
→ Key fields:
   fundingTime → timestamp settlement (ms)
   fundingRate → rate yang dibayarkan
→ Verified: ✅
```

```
GET /fapi/v1/ticker/bookTicker
→ Real-time best bid/ask futures
→ Params: symbol (optional)
→ Key fields:
   bidPrice → best bid
   bidQty   → size di best bid
   askPrice → best ask
   askQty   → size di best ask
→ Verified: ✅
→ Dipakai untuk: spread_futures + slippage_futures
```

```
GET /fapi/v1/exchangeInfo
→ Exchange rules per symbol
→ Key fields per symbol:
   filters → MIN_NOTIONAL (minimum order value)
   status  → TRADING atau tidak
→ Verified: ✅
→ Dipakai untuk: validate min notional saat startup
```

```
GET /fapi/v1/depth
→ Order book depth futures
→ Params: symbol, limit (5, 10, 20, 50, 100, 500, 1000)
→ Key fields:
   bids → [[price, qty], ...]
   asks → [[price, qty], ...]
→ Belum verified dari VPS
→ Dipakai untuk: estimate slippage_futures
```

### Spot — System
```
GET /api/v3/ping
→ Health check spot API
→ Response: {}
→ Verified: ✅
```

### Spot — Market Data
```
GET /api/v3/ticker/bookTicker
→ Real-time best bid/ask spot
→ Params: symbol (optional)
→ Key fields:
   bidPrice → best bid
   bidQty   → size di best bid
   askPrice → best ask
   askQty   → size di best ask
→ Verified: ✅
→ Dipakai untuk: spread_spot + slippage_spot
```

```
GET /api/v3/depth
→ Order book depth spot
→ Params: symbol, limit (5, 10, 20, 50, 100, 500, 1000)
→ Key fields:
   bids → [[price, qty], ...]
   asks → [[price, qty], ...]
→ Belum verified dari VPS
→ Dipakai untuk: estimate slippage_spot
```

---

## PRIVATE ENDPOINTS (Butuh API key + signature)

**Belum di-test dari VPS. Test sebelum Phase 3.**

### Spot — Account
```
GET /api/v3/account
→ Saldo semua asset di spot wallet
→ Key fields:
   balances → [{asset, free, locked}]
→ Auth: required
```

```
GET /api/v3/openOrders
→ List semua open orders spot
→ Params: symbol (optional)
→ Key fields:
   orderId, symbol, side, price, origQty, status
→ Auth: required
→ Dipakai untuk: orphan order detection spot side
```

```
POST /api/v3/order
→ Place spot order
→ Key params:
   symbol, side (BUY/SELL), type (LIMIT/MARKET)
   quantity, price (untuk LIMIT)
   timeInForce (GTC untuk limit)
→ Auth: required
```

```
DELETE /api/v3/order
→ Cancel spot order
→ Key params: symbol, orderId
→ Auth: required
```

### Futures — Account
```
GET /fapi/v2/account
→ Account info futures lengkap
→ Auth: required

GET /fapi/v2/balance
→ Balance per asset di futures wallet
→ Key fields:
   asset, balance, availableBalance
→ Auth: required
```

```
GET /fapi/v1/positionRisk
→ Semua open positions
→ Key fields:
   symbol          → raw format e.g. 'ETHUSDT'
   positionAmt     → size (positif=long, negatif=short)
   entryPrice      → harga entry
   markPrice       → mark price saat ini
   unRealizedProfit
→ Auth: required
→ PENTING: ambil symbol dari pos['info']['symbol']
           BUKAN dari pos['symbol'] (ccxt unified)
```

### Futures — Orders
```
POST /fapi/v1/order
→ Place futures order (BUKAN untuk SL/TP)
→ Key params:
   symbol, side (BUY/SELL), type (LIMIT/MARKET)
   quantity, price (untuk LIMIT)
   timeInForce (GTC untuk limit)
   reduceOnly (True untuk close posisi)
→ Auth: required
```

```
DELETE /fapi/v1/order
→ Cancel futures order
→ Key params: symbol, orderId
→ Auth: required
```

```
GET /fapi/v1/openOrders
→ List open futures orders (BUKAN algo orders)
→ Params: symbol (optional)
→ Auth: required
→ Dipakai untuk: orphan detection regular orders
```

### Futures — Algo Orders (SL/TP)
```
⚠️  WAJIB via requests langsung, BUKAN ccxt
    ccxt tidak support endpoint ini

POST /fapi/v1/algoOrder
→ Place SL atau TP
→ Key params:
   symbol
   side          → BUY atau SELL
   positionSide  → LONG atau SHORT
   quantity
   orderType     → STOP atau TAKE_PROFIT
   stopPrice     → trigger price
   workingType   → "MARK_PRICE" ← WAJIB, bukan CONTRACT_PRICE
                   Alasan: prevent fake spike trigger
→ Returns: dict dengan key 'algoId' — BUKAN 'orderId'
→ Auth: required
```

```
DELETE /fapi/v1/algoOrder
→ Cancel SL atau TP
→ Key params: symbol, algoId ← BUKAN orderId
→ Auth: required
→ JANGAN pakai cancel_order() dari ccxt
  → Wrong endpoint, fail silently tanpa error
```

```
GET /fapi/v1/algo/orders/open
→ List semua open algo orders (SL/TP)
→ Auth: required
→ Dipakai untuk: orphan detection algo orders
→ TERPISAH dari GET /fapi/v1/openOrders
  Dua list yang berbeda, keduanya harus di-check
```

---

## COST MODEL FETCH SEQUENCE

Urutan fetch setiap cycle untuk hitung total RT cost:

```python
# 1. Futures bookTicker (spread + slippage futures)
GET /fapi/v1/ticker/bookTicker?symbol={SYMBOL}
→ spread_futures = (askPrice - bidPrice) / midPrice * 100

# 2. Spot bookTicker (spread + slippage spot)  
GET /api/v3/ticker/bookTicker?symbol={SYMBOL}
→ spread_spot = (askPrice - bidPrice) / midPrice * 100

# 3. Premium index (basis divergence + predicted FR)
GET /fapi/v1/premiumIndex?symbol={SYMBOL}
→ basis = |markPrice - indexPrice| / indexPrice * 100
→ lastFundingRate = FR terakhir yang settled (sebagai proxy)
→ Note: Binance tidak expose "predicted FR" sebagai field explicit
         Gunakan lastFundingRate sebagai approximation
         nextFundingTime untuk tau kapan settlement berikutnya

# 4. Hitung total
total_rt_cost = (
    fee_rt                    # 0.08% fixed
    + (spread_spot * 2)
    + (spread_futures * 2)
    + (slippage_spot * 2)     # estimate dari depth
    + (slippage_futures * 2)  # estimate dari depth
    + basis                   # dari premiumIndex
)

net_expected = predicted_FR - total_rt_cost
```

---

## ERROR CODES YANG RELEVAN

| Code  | Cause | Fix |
|-------|-------|-----|
| -4137 | Stop price already triggered | Skip, log warning |
| -4120 | Pakai /fapi/v1/order untuk algo order | Pakai /fapi/v1/algoOrder |
| -1021 | Timestamp out of sync | Pastikan adjustForTimeDifference=True |
| -1100 | Illegal characters in parameter | Cek format symbol |
| -2010 | Insufficient balance | Cek available balance sebelum order |
| -4003 | Quantity less than min notional | Fetch exchangeInfo, validate dulu |

---

## KNOWN ISSUES DAN WORKAROUNDS

```
1. ccxt version lock: 4.2.86
   Jangan upgrade — versi baru block testnet futures API

2. Position symbol format:
   ccxt unified: pos['symbol']        → 'ETH/USDT:USDT'
   Binance raw:  pos['info']['symbol'] → 'ETHUSDT'
   Selalu pakai raw untuk API calls

3. Order status:
   if order_status in ("filled", "closed"):
       # keduanya = executed

4. Algo orders dan regular orders TERPISAH:
   Orphan detection harus check dua endpoint berbeda

5. SL/TP workingType WAJIB MARK_PRICE:
   Prevent trigger dari candle spike manipulatif
   Set di setiap place_algo_order call

6. recvWindow dan adjustForTimeDifference:
   Wajib di kedua instance (spot + futures)
   Clock VPS sering drift dari Binance server
```

---

## PRIVATE ENDPOINT TEST CHECKLIST

Sebelum Phase 3, verify semua private endpoints accessible dari VPS:

```
□ GET  /api/v3/account          → spot balance
□ GET  /api/v3/openOrders       → spot open orders
□ POST /api/v3/order            → place spot order (testnet)
□ DELETE /api/v3/order          → cancel spot order (testnet)
□ GET  /fapi/v2/balance         → futures balance
□ GET  /fapi/v1/positionRisk    → open positions
□ POST /fapi/v1/order           → place futures order (testnet)
□ DELETE /fapi/v1/order         → cancel futures order (testnet)
□ GET  /fapi/v1/openOrders      → open futures orders
□ POST /fapi/v1/algoOrder       → place SL/TP (testnet)
□ DELETE /fapi/v1/algoOrder     → cancel SL/TP (testnet)
□ GET  /fapi/v1/algo/orders/open → open algo orders
□ GET  /fapi/v1/depth           → order book futures
□ GET  /api/v3/depth            → order book spot
```

Test dilakukan di Phase 3 menggunakan testnet API key dari Futures-agents project.

