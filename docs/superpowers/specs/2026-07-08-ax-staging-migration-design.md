# AX 2012 to Odoo Staging Migration — Design Spec

**Goal:** Extract data from `swa.api.received.data` (received via `/synchronize_data` endpoint) and process it into dedicated staging models for AX 2012 data migration.

**Architecture:** A single controller endpoint `/handle_staging_data` reads unprocessed records from `swa.api.received.data`, routes them by `type_trans` to handler methods, and creates records in the appropriate staging model. Each staging model mirrors the JSON keys from DX 2012 as snake_case fields.

## Data Flow

```
AX 2012 → JSON → /synchronize_data → swa.api.received.data
                                            │ (is_executed='No')
                                            ▼
                                   /handle_staging_data
                                            │
                        ┌───────────────────┼───────────────────┐
                        ▼                   ▼                   ▼
                  ItemStaging        CustVendStaging      InventTransStaging
                  CustInvoiceJourStaging ←→ CustInvoiceTransStaging
```

## Staging Models

All models live under `models/staging/`. Each model has `is_executed` field (Selection: No/Yes, default No).

### `swa.item.staging` — ItemStaging
| Field | Type | JSON Key | Notes |
|---|---|---|---|
| `item_id` | Char | ItemId | |
| `item_name` | Char | ItemName | |
| `unit_id` | Char | UnitId | |
| `type_item` | Char | TypeItem | |
| `is_executed` | Selection | — | No/Yes, default No |

### `swa.cust.vend.staging` — CustVendStaging
| Field | Type | JSON Key | Notes |
|---|---|---|---|
| `cust_vend_id` | Char | CustVendId | |
| `name` | Char | Name | |
| `address` | Text | Address | |
| `address_ext` | Text | AddressExt | |
| `type_cust_vend` | Selection | Type_CustVend | Customer / Vendor |
| `is_executed` | Selection | — | No/Yes, default No |

### `swa.cust.invoice.jour.staging` — CustInvoiceJourStaging
| Field | Type | JSON Key | Notes |
|---|---|---|---|
| `invoice_id` | Char | InvoiceId | |
| `invoice_account` | Char | InvoiceAccount | |
| `incl_tax` | Char | InclTax | |
| `currency` | Char | Currency | |
| `invoice_date` | Date | InvoiceDate | |
| `tax_group` | Char | TaxGroup | |
| `invoice_amount` | Float | InvoiceAmount | |
| `invoice_amount_mst` | Float | InvoiceAmountMST | |
| `tax_amount` | Float | TaxAmount | |
| `is_executed` | Selection | — | No/Yes, default No |
| `line_ids` | One2many | — | → CustInvoiceTrans, via invoice_id+invoice_date |

### `swa.cust.invoice.trans.staging` — CustInvoiceTransStaging
| Field | Type | JSON Key | Notes |
|---|---|---|---|
| `invoice_id` | Char | InvoiceId | |
| `invoice_date` | Date | InvoiceDate | |
| `tax_group` | Char | TaxGroup | |
| `tax_item_group` | Char | TaxItemGroup | |
| `purch_price` | Float | PurchPrice | |
| `line_amount` | Float | LineAmount | |
| `line_amount_mst` | Float | LineAmountMST | |
| `tax_amount` | Float | TaxAmount | |
| `is_executed` | Selection | — | No/Yes, default No |
| `jour_id` | Many2one | — | → CustInvoiceJour |

### `swa.invent.trans.staging` — InventTransStaging
| Field | Type | JSON Key | Notes |
|---|---|---|---|
| `orig_rec_id` | Char | OrigRecId | |
| `no_aju` | Char | NOAju | |
| `bc_type` | Char | BCType | |
| `bc_no` | Char | BCNo | |
| `bc_date` | Char | BCDate | |
| `invoice_id` | Char | InvoiceId | |
| `trans_no` | Char | TransNo | |
| `netto` | Float | Netto | |
| `item_id` | Char | ItemId | |
| `inventserial` | Char | inventserial | |
| `site` | Char | Site | |
| `warehouse` | Char | Warehouse | |
| `warehouse_type` | Char | WarehouseType | |
| `location` | Char | Location | |
| `invent_batch_id` | Char | InventBatchId | |
| `transtype` | Char | Transtype | |
| `modified_by` | Char | ModifiedBy | |
| `modified_date_time` | Char | ModifiedDateTime | |
| `cust_vend_id` | Char | CustVendId | |
| `doc_no` | Char | DocNo | |
| `doc_date` | Char | DocDate | |
| `no_faktur_pajak` | Char | NoFakturPajak | |
| `qty` | Float | Qty | |
| `trans_date` | Date | TransDate | |
| `trans_unit` | Char | TransUnit | |
| `trans_qty` | Float | TransQty | |
| `journal_inv_type` | Char | journalInvType | |
| `invent_ref_id` | Char | InventRefId | |
| `currency` | Char | Currency | |
| `cost_price` | Float | CostPrice | |
| `cost_amount` | Float | CostAmount | |
| `packing_slip_id` | Char | PackingSlipId | |
| `peb` | Char | PEB | |
| `is_executed` | Selection | — | No/Yes, default No |

## Controller

**Endpoint:** `POST /handle_staging_data` (auth='none', csrf=False)

**Flow:**
1. Authenticate user (header-based or public)
2. Fetch records from `swa.api.received.data` where `is_executed = 'No'`
3. For each record:
   a. Parse `data_trans` (JSON string → list of dicts)
   b. Route by `type_trans`:
      - `'Item'` → `_process_item_staging(data)`
      - `'CustVend'` → `_process_cust_vend_staging(data)`
      - `'InventTrans'` → `_process_invent_trans_staging(data)`
      - `'CustInvoiceJour'` → `_process_cust_invoice_jour_staging(data)`
      - `'CustInvoiceTrans'` → `_process_cust_invoice_trans_staging(data)`
   c. Mark record `is_executed = 'Yes'`
4. Return JSON response

**Helper methods:**
- `authenticate_user()` — authenticate from request headers
- `process_data(model, domain, limit=500)` — search and fetch records
- `create_record(model, values)` — create staging record
- `update_record_status(record, status)` — update is_executed
- `_convert_keys(data)` — convert CamelCase keys to snake_case

## Views & Menu

Views in `views/staging/`.

**Menu structure:**
```
[Synchronize] ← app bar
├── Item Staging            → swa.item.staging (tree+form)
├── CustVend Staging        → swa.cust.vend.staging (tree+form)
├── InventTrans Staging     → swa.invent.trans.staging (tree+form)
└── CustInvoiceJour Staging → swa.cust.invoice.jour.staging (tree+form, with trans lines)
```

**CustInvoiceTrans** — no separate menu/view. Displayed as one2many list inside CustInvoiceJour form (in a notebook tab).

All staging views are **read-only** in tree view (create="false", edit="false", delete="false").

## Files

| Action | File |
|--------|------|
| Create | `models/staging/__init__.py` |
| Create | `models/staging/item_staging.py` |
| Create | `models/staging/cust_vend_staging.py` |
| Create | `models/staging/cust_invoice_jour_staging.py` |
| Create | `models/staging/cust_invoice_trans_staging.py` |
| Create | `models/staging/invent_trans_staging.py` |
| Modify | `models/__init__.py` |
| Modify | `security/ir.model.access.csv` |
| Modify | `controllers/controllers.py` (add handle_staging_data endpoint) |
| Create | `views/staging/item_staging_views.xml` |
| Create | `views/staging/cust_vend_staging_views.xml` |
| Create | `views/staging/cust_invoice_jour_staging_views.xml` |
| Create | `views/staging/invent_trans_staging_views.xml` |
| Modify | `__manifest__.py` |
