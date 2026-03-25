# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import calendar


class AzFohProductionPrice(models.Model):
    _name = "az.foh.production.price"
    _description = "FOH Production Price (Intermediate)"
    _rec_name = "mrp_production_id"
    _order = "trans_date desc, mrp_production_id"

    # ─────────────────────────────────────────────────────────────────────
    # Fields
    # ─────────────────────────────────────────────────────────────────────

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    trans_date = fields.Date(
        string="Trans Date",
    )
    mrp_production_id = fields.Many2one(
        comodel_name="mrp.production",
        string="Production Order",
        ondelete="restrict",
    )
    lot_id = fields.Many2one(
        comodel_name="stock.lot",
        string="Lot/Serial (Finished Good)",
        ondelete="restrict",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Finished Good",
        ondelete="restrict",
    )
    product_default_code = fields.Char(
        string="Product Code",
        related="product_id.default_code",
        readonly=True,
    )
    product_name = fields.Char(
        string="Product Name",
        related="product_id.name",
        readonly=True,
    )
    location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Location",
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
    )
    uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="UOM",
        related="product_id.uom_id",
        readonly=True,
        store=True,
    )
    qty_producing = fields.Float(
        string="Qty Producing",
        digits=(16, 4),
        default=0.0,
    )
    rm_cost = fields.Float(
        string="Raw Material Cost",
        digits=(16, 2),
        default=0.0,
    )
    foh_cost = fields.Float(
        string="FOH Cost",
        digits=(16, 2),
        default=0.0,
    )
    total_cost = fields.Float(
        string="Total Cost",
        digits=(16, 2),
        compute="_compute_total_cost",
        store=True,
    )

    # ─────────────────────────────────────────────────────────────────────
    # Computed
    # ─────────────────────────────────────────────────────────────────────

    @api.depends("rm_cost", "foh_cost")
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = rec.rm_cost + rec.foh_cost

    # ─────────────────────────────────────────────────────────────────────
    # Business Logic
    # ─────────────────────────────────────────────────────────────────────

    @api.model
    def generate_from_productions(self, productions):
        """
        Populate az_foh_production_price from a recordset of mrp.production.

        rm_cost = Σ (qty × price) from raw material stock.move lines (Done)
        foh_cost = Σ cost_price_foh from az.foh.production.cost per MRP

        Existing records for the same MRP orders are deleted before regenerating.
        """
        if not productions:
            return False

        # Remove old records for the same MRP orders
        self.search([("mrp_production_id", "in", productions.ids)]).unlink()

        vals_list = []
        for mrp in productions:
            qty_producing = mrp.qty_producing or 0.0
            if qty_producing <= 0:
                continue

            # trans_date = LAST DAY of mrp.date_start's month
            from datetime import date as dt_date
            mrp_date = mrp.date_start.date() if mrp.date_start else fields.Date.today()
            last_day = calendar.monthrange(mrp_date.year, mrp_date.month)[1]
            trans_date = dt_date(mrp_date.year, mrp_date.month, last_day)

            # Duplicate validation
            if self.search([
                ("trans_date", "=", trans_date),
                ("mrp_production_id", "=", mrp.id),
                ("product_id", "=", mrp.product_id.id),
            ], limit=1):
                raise ValidationError(
                    _("FOH Production Price already exists for MRP '%s' / product '%s' on %s.\n"
                      "Please delete the existing data first.")
                    % (mrp.name, mrp.product_id.display_name, trans_date)
                )

            # ── STEP 1: Raw material cost ──────────────────────────────────
            total_rm_cost = 0.0
            raw_moves = mrp.move_raw_ids.filtered(lambda m: m.state == "done")
            for move in raw_moves:
                for ml in move.move_line_ids:
                    qty = ml.quantity
                    if qty <= 0:
                        continue
                    product = ml.product_id
                    if product.tracking == "lot" and ml.lot_id:
                        price = (
                            ml.lot_id.standard_price
                            if hasattr(ml.lot_id, "standard_price")
                            and ml.lot_id.standard_price
                            else product.standard_price
                        )
                    else:
                        price = product.standard_price
                    total_rm_cost += qty * price

            # ── STEP 2: FOH cost for this MRP ─────────────────────────────
            foh_records = self.env["az.foh.production.cost"].search(
                [("mrp_production_id", "=", mrp.id)]
            )
            total_foh_cost = sum(foh_records.mapped("cost_price_foh"))

            vals_list.append(
                {
                    "company_id": mrp.company_id.id or self.env.company.id,
                    "trans_date": trans_date,
                    "mrp_production_id": mrp.id,
                    "lot_id": mrp.lot_producing_id.id if mrp.lot_producing_id else False,
                    "product_id": mrp.product_id.id,
                    "location_id": mrp.location_dest_id.id
                    if mrp.location_dest_id
                    else False,
                    "qty_producing": qty_producing,
                    "rm_cost": total_rm_cost,
                    "foh_cost": total_foh_cost,
                }
            )

        if not vals_list:
            raise UserError(
                _(
                    "No valid production data found. "
                    "Make sure qty_producing > 0 and raw material moves are Done."
                )
            )

        self.create(vals_list)
        return True

    @api.model
    def generate_from_production_cost_batch(self, record_ids):
        """
        Called from JavaScript (az_foh_production_cost list view) with
        selected record IDs of az.foh.production.cost.
        Derives MRP orders from those records, then regenerates
        az_foh_production_price.
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

        return self.generate_from_productions(productions)
