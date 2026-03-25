# FOH Calculation Flow — Roles & Notes

Dokumen ini menjelaskan alur lengkap perhitungan **Factory Overhead (FOH)** dan **Harga Pokok Produksi (HPP)** pada modul `swa_acc`.

---

## Alur Utama (5 Tahap)

```
[1] FOH Item Cost Price
        ↓  Generate FOH Production Cost (Wizard)
[2] FOH Production Cost
        ↓  recalculate_cost_fg() — otomatis
[3] FOH Production Price  ← REVIEW di sini
        ↓  Button: Calculate Average Product
[4] FOH Product Average Cost Price
        ↓  Button: Update Standard Price
[5] product.product / stock.lot .standard_price
```

---

## Detail Per Model

### [1] `az.foh.item.cost.price`
- Diisi manual / wizard.
- Berisi **harga satuan FOH** (listrik, bahan bakar, dll.) per produk FOH, per lokasi, per periode.

### [2] `az.foh.production.cost`
- Di-generate oleh **wizard "Generate FOH Production Cost"** (`az.foh.generate.mrp.wizard`).
- Satu baris = satu FOH item × satu MRP production order.
- Field penting: `mrp_production_id`, `lot_id`, `product_id_foh`, `cost_price_foh`.

### [3] `az.foh.production.price` *(tabel intermediate)*
- Dibuat **otomatis** saat wizard selesai via `recalculate_cost_fg()`.
- Satu baris = **satu MRP order** (bukan per FOH item).
- Field:

| Field | Sumber |
|---|---|
| `trans_date` | `mrp.date_start` |
| `product_id` | `mrp.product_id` (FG) |
| `lot_id` | `mrp.lot_producing_id` |
| `location_id` | `mrp.location_dest_id` |
| `qty_producing` | `mrp.qty_producing` |
| `rm_cost` | Σ `(qty × price)` dari `stock.move` raw material (Done) |
| `foh_cost` | Σ `cost_price_foh` dari `az_foh_production_cost` per MRP |
| `total_cost` | `rm_cost + foh_cost` (computed) |

> **User bisa review data di sini sebelum di-average.**

### [4] `az.foh.cost.price.fg`
- Diisi via button **"Calculate Average Product"** dari view `az_foh_production_price`.
- Rumus:
  ```
  avg_cost_per_unit = Σ(total_cost) / Σ(qty_producing)
  group by: product_id + trans_date + location_id + lot_id
  ```
- `cost_price_before_foh` = `lot.standard_price` (jika lot tersedia) atau `product.standard_price`.
- `cost_price_after_foh` = hasil average di atas.
- Unique constraint: `(trans_date, product_id, location_id, lot_id)` → upsert (update jika sudah ada).

### [5] Update Standard Price
- Button **"Update Standard Price"** di view `az_foh_cost_price_fg`.
- Jika `lot_id` ada → update `lot.standard_price` langsung.
- Jika tidak ada lot → update `product.standard_price`.

---

## Harga Sebelum vs Sesudah FOH

| Field | Artinya |
|---|---|
| `cost_price_before_foh` | Harga standar sebelum FOH ditambahkan (dari `standard_price` saat ini) |
| `cost_price_after_foh` | Harga standar baru setelah FOH = `avg_cost_per_unit` |

---

## Reset Data (Wizard "Remove MRP & Inventory Data")

Tombol ini menghapus secara berurutan (child → parent):

1. `az_foh_cost_price_fg`
2. `az_foh_production_price`
3. `az_foh_production_cost`
4. `az_foh_item_cost_price`
5. `az_foh_calculation`
6. MRP data: `mrp_workcenter_productivity` → `mrp_workorder` → `stock_move_line` (MRP) → `stock_move` (MRP) → `mrp_production`
7. Inventory: `stock_move_line` → `stock_move` → `stock_picking` → `stock_quant` (internal) → `stock_valuation_layer`
8. Reset sequences (`mrp.*`, `stock.*`, `WH/`)

---

## Button Summary

| View | Button | Action |
|---|---|---|
| FOH Production Cost | Generate FOH Production Cost | Buka wizard generate |
| FOH Production Price | **Calculate Average Product** | Average total_cost/qty → `az_foh_cost_price_fg` |
| FOH Product Average Cost Price | **Update Standard Price** | Tulis `cost_price_after_foh` → `standard_price` |
