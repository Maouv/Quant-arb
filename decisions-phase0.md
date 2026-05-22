# DECISIONS — Post Phase 0 Brainstorming
**Date:** 21 May 2026
**Participants:** Maou, Kiro

---

## KEPUTUSAN YANG DISETUJUI BERSAMA

### 1. Survivorship Bias — Known Limitation
**Status:** Acknowledged, partially addressed

**Masalah:**
Universe 11 coin yang dipilih adalah coin yang masih ada dan liquid di Mei 2026. Coin yang delist/collapse tidak ada di universe — bisa membuat yield historis terlihat lebih baik dari realitanya.

**Kesepakatan:**
- Tidak bisa fix dengan note saja (live mode pakai uang asli)
- Tidak bisa fix dengan backward-looking correction karena data coin delist tidak tersedia
- Solusi: **Synthetic stress test di Phase 3** — simulate coin collapse + delist scenario
- **Deep dive diperlukan** sebelum pakai synthetic data untuk memastikan tidak bias ke arah yang kita mau

**Target Phase:** Phase 3 backlog

---

### 2. Cost Sampling Underestimate Saat FR Spike
**Status:** Acknowledged, already covered

**Masalah:**
Cost model di-sample 5x di hari normal (19 Mei 2026). Saat FR spike tinggi (justru saat entry), spread/slippage kemungkinan jauh lebih tinggi karena semua arb trader masuk bersamaan.

**Kesepakatan:**
- Sudah ter-cover oleh **cost multiplier stress test 3x/5x/10x** di rejection criteria
- Di Phase 1: validate apakah range multiplier ini realistis dari distribusi FR spike vs normal

**Target Phase:** Phase 1 validation

---

### 3. Buffer Adequacy — Margin Call Threshold
**Status:** To be derived

**Masalah:**
Phase 0 menspesifikasikan 40% buffer capital, tapi belum ada hitungan berapa % price move yang akan exhaust buffer pada position size $500.

**Kesepakatan:**
- Masuk Phase 2 math framework
- Deliverable: "max price move sebelum margin call pada $500 position dengan 40% buffer"

**Target Phase:** Phase 2

---

### 4. Rejection Criteria — Absolute Floor
**Status:** To be derived

**Masalah:**
Rejection criteria #4: "Paper trading yield < 50% backtest → reject" adalah relative threshold. Tidak address apakah absolute yield masih worth the risk.

**Kesepakatan:**
- Tambah **absolute floor** — bukan cuma relative
- Angka absolute floor di-derive dari Phase 1 data (historical yield distribution)
- Dua layer: relative (50% backtest) + absolute (TBD dari data)

**Target Phase:** Phase 1 → derive angka, update rejection criteria

---

### 5. Validation Set Data Gap
**Status:** To be fixed now

**Masalah:**
Validation set 2025 hanya sampai Mei 2025, bukan Desember 2025. Script download hardcode stop di `month > 5`.

**Kesepakatan:**
- Download sisa 2025 (Juni-Desember)
- Download 2026 Jan-April untuk test set (tapi tidak dipakai sampai Phase 4)

**Target Phase:** Immediate fix before Phase 1

---

## BACKLOG (Perlu Deep Dive)

| Item | Target Phase | Status |
|------|--------------|--------|
| Synthetic data methodology untuk survivorship stress test | Phase 3 | Pending deep dive |
| Buffer adequacy calculation | Phase 2 | Pending |
| Absolute floor untuk rejection criteria | Phase 1 | Pending data |

---

## CATATAN

Keputusan di atas adalah hasil brainstorming dua arah — bukan satu pihak saja yang prove. Setiap item sudah di-challenge dan disetujui bersama sebelum masuk dokumen ini.
