# PHASE 4 HANDOFF — 03: API REFERENCE
**Date:** 23 May 2026
**Source:** phase0-api-docs.md (verified 19 May 2026)

---

## LIBRARY

```
ccxt == 4.2.86   ← LOCKED, jangan upgrade
                   Versi baru block testnet futures API
requests         ← untuk algo orders (ccxt tidak support)
python-dotenv    ← untuk load secrets.env
```

---

## BASE URLS

```python
BASE_SPOT              = "https://api.binance.com"
BASE_FUTURES           = "https://fapi.binance.com"
BASE_TESTNET_FUTURES   = "https://testnet.binancefuture.com"
BASE_TESTNET_SPOT      = "https://testnet.binance.vision"
```

---

## DUA INSTANCE ccxt — WAJIB TERPISAH

```python
import ccxt

spotExchange = ccxt.binance({
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "options": {"defaultType": "spot"},
    "recvWindow": 60000,              # WAJIB — clock drift VPS
    "adjustForTimeDifference": True,  # WAJIB — clock drift VPS
})

futuresExchange = ccxt.binanceusdm({
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "options": {"defaultType": "future"},
    "recvWindow": 60000,
    "adjustForTimeDifference": True,
})
```

---

## PUBLIC ENDPOINTS

### Scan FR semua coins sekaligus (UTAMA — pakai ini, bukan per-coin)
```
GET /fapi/v1/premiumIndex
→ Tidak perlu symbol param → return semua coins
→ Key fields per coin:
   symbol          → "ETHUSDT"
   markPrice       → mark price (untuk SL/TP reference)
   indexPrice      → harga spot index
   lastFundingRate → FR terakhir yang settled (dalam desimal, kalikan 100 untuk %)
   nextFundingTime → timestamp settlement berikutnya (ms)
→ Verified: ✅
```

### Real-time bid/ask futures (untuk spread + slippage)
```
GET /fapi/v1/ticker/bookTicker
→ Tidak perlu symbol param → return semua coins sekaligus
→ Key fields: bidPrice, bidQty, askPrice, askQty
→ Verified: ✅
```

### Real-time bid/ask spot
```
GET /api/v3/ticker/bookTicker
→ Return semua coins sekaligus
→ Key fields: bidPrice, bidQty, askPrice, askQty
→ Verified: ✅
```

### Order book depth (untuk estimate slippage)
```
GET /fapi/v1/depth?symbol=ETHUSDT&limit=20
GET /api/v3/depth?symbol=ETHUSDT&limit=20
→ Key fields:
   bids → [[price, qty], ...]
   asks → [[price, qty], ...]
→ Belum verified dari VPS — test dulu di test_connectivity.py
```

### Exchange info (min notional — fetch saat startup saja)
```
GET /fapi/v1/exchangeInfo
→ Key fields per symbol:
   filters → MIN_NOTIONAL
   status  → "TRADING" atau tidak
→ Verified: ✅
```

---

## PRIVATE ENDPOINTS

### Balance
```
GET /fapi/v2/balance
→ Key fields: asset, balance, availableBalance

GET /api/v3/account
→ Key fields: balances → [{asset, free, locked}]
```

### Open Positions
```
GET /fapi/v1/positionRisk
→ Key fields:
   symbol          → raw format "ETHUSDT" (BUKAN ccxt unified "ETH/USDT:USDT")
   positionAmt     → size (positif=long, negatif=short)
   entryPrice
   markPrice
   unRealizedProfit
→ PENTING: pakai pos['info']['symbol'], BUKAN pos['symbol']
```

### Place Orders
```
POST /api/v3/order           → spot order (via ccxt)
POST /fapi/v1/order          → futures order (via ccxt, BUKAN untuk SL/TP)

Key params:
  symbol, side (BUY/SELL), type (LIMIT/MARKET)
  quantity, price (untuk LIMIT)
  timeInForce: GTC (untuk limit order)
  reduceOnly: True (untuk close posisi futures)
```

### Open Orders (regular — bukan algo)
```
GET /fapi/v1/openOrders      → futures regular orders
GET /api/v3/openOrders       → spot orders
→ Dipakai untuk: orphan detection
```

### Cancel Orders (regular)
```
DELETE /fapi/v1/order        → cancel futures order
DELETE /api/v3/order         → cancel spot order
→ Key params: symbol, orderId
```

---

## ALGO ORDERS (SL/TP) — WAJIB VIA REQUESTS, BUKAN ccxt

ccxt tidak support endpoint ini. Gunakan requests langsung.

### Place SL/TP
```
POST /fapi/v1/algoOrder

params = {
    "symbol":       "ETHUSDT",
    "side":         "BUY",           # BUY untuk close short, SELL untuk close long
    "positionSide": "SHORT",         # atau "LONG"
    "quantity":     "0.1",
    "orderType":    "STOP",          # atau "TAKE_PROFIT"
    "stopPrice":    "3000.00",
    "workingType":  "MARK_PRICE",    # WAJIB — bukan CONTRACT_PRICE
                                     # Alasan: prevent trigger dari candle spike manipulatif
}

Response: {"algoId": 12345, ...}
→ Simpan algoId — ini yang dipakai untuk cancel
→ BUKAN orderId
```

### Cancel SL/TP
```
DELETE /fapi/v1/algoOrder
→ Key params: symbol, algoId
→ JANGAN pakai cancel_order() dari ccxt
  → Wrong endpoint, fail silently tanpa error
```

### List Open Algo Orders
```
GET /fapi/v1/algo/orders/open
→ TERPISAH dari GET /fapi/v1/openOrders
→ Keduanya harus di-check saat orphan detection
→ Response: {"orders": [{algoId, symbol, side, ...}]}
```

---

## SLIPPAGE ESTIMATION

Scan order book untuk estimate slippage pada $150 position:

```python
def estimateSlippage(asks: list, bids: list, positionSize: float) -> float:
    """
    Scan asks dari best ask, accumulate sampai positionSize terpenuhi.
    Return slippage % = (worst_fill - mid_price) / mid_price * 100
    """
    bestBid = float(bids[0][0])
    bestAsk = float(asks[0][0])
    midPrice = (bestBid + bestAsk) / 2

    cumulative = 0.0
    worstPrice = bestAsk
    for price, qty in asks:
        cumulative += float(price) * float(qty)
        worstPrice = float(price)
        if cumulative >= positionSize:
            break
    return (worstPrice - midPrice) / midPrice * 100
```

---

## ORDER STATUS

```python
if orderStatus in ("filled", "closed"):
    # keduanya = executed, treat sama
```

---

## ERROR CODES

| Code  | Cause | Fix |
|-------|-------|-----|
| -4137 | Stop price already triggered | Skip, log warning |
| -4120 | Pakai /fapi/v1/order untuk algo | Pakai /fapi/v1/algoOrder |
| -1021 | Timestamp out of sync | Pastikan adjustForTimeDifference=True |
| -1100 | Illegal characters in parameter | Cek format symbol |
| -2010 | Insufficient balance | Cek availableBalance sebelum order |
| -4003 | Quantity less than min notional | Fetch exchangeInfo, validate dulu |

---

## PRIVATE ENDPOINT TEST CHECKLIST

Jalankan test_connectivity.py sebelum bot jalan:

```
□ GET  /api/v3/account
□ GET  /api/v3/openOrders
□ POST /api/v3/order              (testnet — place dan cancel order kecil)
□ DELETE /api/v3/order
□ GET  /fapi/v2/balance
□ GET  /fapi/v1/positionRisk
□ POST /fapi/v1/order             (testnet)
□ DELETE /fapi/v1/order
□ GET  /fapi/v1/openOrders
□ POST /fapi/v1/algoOrder         (testnet)
□ DELETE /fapi/v1/algoOrder       (testnet — pakai algoId)
□ GET  /fapi/v1/algo/orders/open
□ GET  /fapi/v1/depth
□ GET  /api/v3/depth
```
