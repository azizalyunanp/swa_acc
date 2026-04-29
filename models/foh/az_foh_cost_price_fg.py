# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AzFohCostPriceFg(models.Model):
    _name = "az.foh.cost.price.fg"
    _description = "FOH Product Average Cost Price"
    _rec_name = "product_id"
    _order = "trans_date desc, product_id"

    trans_date = fields.Date(
        string="Trans Date",
        required=True,
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        required=True,
        ondelete="restrict",
    )
    product_name = fields.Char(
        string="Product Name",
        related="product_id.name",
        readonly=True,
    )
    default_code = fields.Char(
        string="Product Code",
        related="product_id.default_code",
        readonly=True,
    )
    location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Location",
        required=True,
        ondelete="restrict",
    )
    location_name = fields.Char(
        string="Location Name",
        related="location_id.name",
        readonly=True,
    )
    uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="UOM",
        related="product_id.uom_id",
        readonly=True,
        store=True,
    )
    cost_price_before_foh = fields.Float(
        string="Cost Price Before FOH",
        digits=(16, 2),
        default=0.0,
    )
    cost_price_after_foh = fields.Float(
        string="Cost Price After FOH",
        digits=(16, 2),
        default=0.0,
    )
    status = fields.Selection(
        selection=[
            ("done", "Done"),
            ("canceled", "Canceled"),
        ],
        string="Status",
        default="done",
        required=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )

    lot_id = fields.Many2one(
        comodel_name="stock.lot",
        string="Lot/Serial",
        ondelete="restrict",
    )

    _sql_constraints = [
        (
            "unique_trans_product_location_lot",
            "UNIQUE(trans_date, product_id, location_id, lot_id)",
            "A record with the same Trans Date, Product, Location, and Lot already exists!",
        ),
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # Update Standard Price
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def update_standard_price_batch(self, record_ids):
        """
        Batch method to update standard_price from selected records.
        Called from JavaScript with selected record IDs.
        """
        if not record_ids:
            return False

        records = self.browse(record_ids)
        for record in records:
            record._update_standard_price()
        return True

    def _update_standard_price(self):
        self.ensure_one()

        product = self.product_id
        new_price = self.cost_price_after_foh

        if not product or not new_price:
            return False

        if product.cost_method != 'average':
            # Non-AVCO: tulis biasa cukup
            product.sudo().with_context(disable_auto_svl=True).write({"standard_price": new_price})
            return True

        if product.tracking == 'lot' and self.lot_id:
            # Update standard_price di lot level (untuk referensi)
            if hasattr(self.lot_id, 'standard_price'):
                self.lot_id.sudo().with_context(disable_auto_svl=True).write({"standard_price": new_price})

            # Hitung nilai stok khusus lot ini
            quants = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('lot_id', '=', self.lot_id.id),
                ('location_id.usage', '=', 'internal'),
            ])
            qty_on_hand = sum(quants.mapped('quantity'))

            if qty_on_hand > 0:
                old_price = product.standard_price
                price_diff = new_price - old_price
                revaluation_value = round(price_diff * qty_on_hand, 2)

                if revaluation_value != 0:
                    self._create_revaluation_entry(
                        product, self.lot_id, revaluation_value
                    )

            # Update standard_price product juga agar AVCO konsisten
            product.sudo().with_context(disable_auto_svl=True).write({"standard_price": new_price})

        else:
            # Tidak ada lot tracking → pakai method bawaan Odoo
            product.sudo()._change_standard_price(new_price)

        return True


    def _create_revaluation_entry(self, product, lot, revaluation_value):
        category = product.categ_id
        stock_valuation_account = category.property_stock_valuation_account_id

        # Akun offset/counter-part untuk FOH revaluation.
        # Di-set manual per Product Category via field az_foh_account_id.
        price_diff_account = category.az_foh_account_id

        if not stock_valuation_account:
            raise UserError(
                "Stock Valuation Account belum di-set di Product Category: %s"
                % category.name
            )
        if not price_diff_account:
            raise UserError(
                "FOH Revaluation Account (az_foh_account_id) belum di-set "
                "di Product Category: %s."
                % category.name
            )

        if revaluation_value > 0:
            debit_account  = stock_valuation_account
            credit_account = price_diff_account
        else:
            debit_account  = price_diff_account
            credit_account = stock_valuation_account

        # Create Stock Valuation Layer to match the accounting entry
        svl_vals = {
            'company_id': self.env.company.id,
            'product_id': product.id,
            'description': 'Revaluation: %s - Lot: %s' % (product.name, lot.name),
            'value': revaluation_value,
            'quantity': 0,
            'lot_id': lot.id if lot else False,
        }
        svl = self.env['stock.valuation.layer'].sudo().create(svl_vals)

        move_vals = {
            'ref': 'Revaluation: %s - Lot: %s' % (product.name, lot.name),
            'journal_id': category.property_stock_journal.id,
            'stock_valuation_layer_ids': [(6, 0, [svl.id])],
            'line_ids': [
                (0, 0, {
                    'name': 'Stock Revaluation %s [%s]' % (product.name, lot.name),
                    'account_id': debit_account.id,
                    'debit': abs(revaluation_value),
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': 'Stock Revaluation %s [%s]' % (product.name, lot.name),
                    'account_id': credit_account.id,
                    'debit': 0.0,
                    'credit': abs(revaluation_value),
                }),
            ],
        }

        move = self.env['account.move'].sudo().create(move_vals)
        move.sudo().action_post()
        return move
    
    # ─────────────────────────────────────────────────────────────────────────
    # Calculate Average Product (NEW: reads from az_foh_production_price)
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def calculate_average_from_production_price(self, production_price_ids):
        """
        Calculate average product cost from selected az_foh_production_price records
        and write results into az_foh_cost_price_fg.

        Called from JavaScript in the az_foh_production_price list view.

        Formula:
          avg_cost_per_unit = Σ(total_cost) / Σ(qty_producing)
          grouped by (product_id, trans_date, location_id)
        """
        if not production_price_ids:
            return False

        price_records = self.env["az.foh.production.price"].browse(
            production_price_ids
        )

        if not price_records:
            raise UserError(_("No Production Price records found."))

        return self._calculate_and_upsert(price_records)

    @api.model
    def calculate_average_product_batch(self, record_ids):
        """
        Batch method called from JavaScript on az_foh_production_cost list view.
        Kept for backward compatibility.

        Workflow:
          1. Get MRP orders from selected az_foh_production_cost records.
          2. Regenerate az_foh_production_price for those MRP orders.
          3. Calculate average and upsert into az_foh_cost_price_fg.
        """
        if not record_ids:
            return False

        productions = (
            self.env["az.foh.production.cost"]
            .browse(record_ids)
            .mapped("mrp_production_id")
        )

        if not productions:
            raise UserError(_("No Production Order linked to the selected records."))

        # Step 1: (Re)generate az_foh_production_price for these MRPs
        self.env["az.foh.production.price"].generate_from_productions(productions)

        # Step 2: Calculate average from the newly generated records
        price_records = self.env["az.foh.production.price"].search(
            [("mrp_production_id", "in", productions.ids)]
        )

        if not price_records:
            raise UserError(
                _(
                    "No Production Price records generated. "
                    "Please check that raw material moves are Done."
                )
            )

        return self._calculate_and_upsert(price_records)

    def _calculate_and_upsert(self, price_records):
        """
        Core calculation: group az_foh_production_price records by
        (product_id, trans_date, location_id), compute avg_cost_per_unit,
        then create or update az_foh_cost_price_fg.
        """
        aggregation = {}
        for rec in price_records:
            if not rec.product_id or not rec.location_id:
                continue

            key = (
                rec.product_id.id,
                rec.trans_date,
                rec.location_id.id,
                rec.lot_id.id if rec.lot_id else False,
            )

            if key not in aggregation:
                aggregation[key] = {
                    "product_id": rec.product_id,
                    "trans_date": rec.trans_date,
                    "location_id": rec.location_id,
                    "lot_id": rec.lot_id,
                    "company_id": rec.company_id,
                    "total_cost_sum": 0.0,
                    "total_qty_sum": 0.0,
                }

            aggregation[key]["total_cost_sum"] += rec.total_cost
            aggregation[key]["total_qty_sum"] += rec.qty_producing

        if not aggregation:
            raise UserError(
                _(
                    "No valid data to aggregate. "
                    "Make sure products have a location assigned in the production orders."
                )
            )

        for key, data in aggregation.items():
            product = data["product_id"]
            trans_date = data["trans_date"]
            location = data["location_id"]
            company = data["company_id"]
            total_qty = data["total_qty_sum"]
            total_cost = data["total_cost_sum"]

            if total_qty <= 0:
                continue

            avg_cost_per_unit = round(total_cost / total_qty, 2)

            lot = data.get("lot_id")  # may be empty recordset

            # Determine cost_price_before_foh: prefer specific lot, then search, then product
            if lot and hasattr(lot, "standard_price"):
                cost_price_before = lot.standard_price or product.standard_price
            elif product.tracking == "lot":
                lots = self.env["stock.lot"].search(
                    [
                        ("product_id", "=", product.id),
                        ("company_id", "=", company.id),
                    ],
                    limit=1,
                )
                cost_price_before = (
                    lots[0].standard_price
                    if lots and hasattr(lots[0], "standard_price")
                    else product.standard_price
                )
            else:
                cost_price_before = product.standard_price

            # Upsert into az_foh_cost_price_fg
            existing = self.search(
                [
                    ("trans_date", "=", trans_date),
                    ("product_id", "=", product.id),
                    ("location_id", "=", location.id),
                    ("lot_id", "=", lot.id if lot else False),
                ],
                limit=1,
            )

            vals = {
                "lot_id": lot.id if lot else False,
                "cost_price_before_foh": cost_price_before,
                "cost_price_after_foh": avg_cost_per_unit,
                "status": "done",
            }

            if existing:
                existing.write(vals)
            else:
                vals.update(
                    {
                        "trans_date": trans_date,
                        "product_id": product.id,
                        "location_id": location.id,
                        "company_id": company.id if company else self.env.company.id,
                    }
                )
                self.create(vals)

        return True
