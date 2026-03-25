# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import calendar


class AzFohGenerateMrpWizard(models.TransientModel):
    _name = "az.foh.generate.mrp.wizard"
    _description = "Generate FOH Production Cost Wizard"

    from_date = fields.Date(string="From Date", required=True)
    to_date = fields.Date(string="To Date", required=True)
    location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Location",
        required=True,
        domain=[("usage", "=", "internal")],
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    def generate_foh_production_cost(self):
        self.ensure_one()

        if self.from_date > self.to_date:
            raise UserError(_("From Date cannot be greater than To Date."))

        # ─────────────────────────────────────────────────────────────
        # STEP 1: Get done MRP productions within date range & location
        # ─────────────────────────────────────────────────────────────
        productions = self.env["mrp.production"].search(
            [
                ("state", "=", "done"),
                ("date_start", ">=", self.from_date),
                ("date_start", "<=", self.to_date),
                ("location_dest_id", "=", self.location_id.id),
            ]
        )

        if not productions:
            raise UserError(
                _(
                    "No finished production orders found for the given "
                    "period and location."
                )
            )

        # ─────────────────────────────────────────────────────────────
        # STEP 2: Delete existing records for the same period & location
        # ─────────────────────────────────────────────────────────────
        self.env["az.foh.production.cost"].search(
            [
                ("trans_date", ">=", self.from_date),
                ("trans_date", "<=", self.to_date),
                ("location_id", "=", self.location_id.id),
            ]
        ).unlink()

        # ─────────────────────────────────────────────────────────────
        # STEP 3: For each production, match FOH Item Cost Price records
        # ─────────────────────────────────────────────────────────────
        vals_list = []
        for mrp in productions:
            # Determine trans_date as LAST DAY of the MRP's month
            mrp_date = mrp.date_start.date() if mrp.date_start else self.to_date
            last_day = calendar.monthrange(mrp_date.year, mrp_date.month)[1]
            from datetime import date as dt_date
            trans_date = dt_date(mrp_date.year, mrp_date.month, last_day)

            # Get az.foh.item.cost.price records for this product & location
            foh_costs = self.env["az.foh.item.cost.price"].search(
                [
                    ("product_id", "=", mrp.product_id.id),
                    ("location_id", "=", self.location_id.id),
                    ("trans_date", ">=", self.from_date),
                    ("trans_date", "<=", self.to_date),
                ]
            )

            if not foh_costs:
                continue

            # Get unit_cost from stock.valuation.layer for this MRP
            # stock.valuation.layer links to account.move via stock.move
            # Reference production's finished move to get valuation
            svl = self.env["stock.valuation.layer"].search(
                [
                    ("reference", "=", mrp.name),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=1,
            )
            unit_cost = svl.unit_cost if svl else 0.0

            for foh_cost in foh_costs:
                vals_list.append(
                    {
                        "trans_date": trans_date,
                        "location_id": self.location_id.id,
                        "company_id": self.company_id.id,
                        "mrp_production_id": mrp.id,
                        "product_id_foh": foh_cost.product_id_foh.id,
                        "product_foh_qty": mrp.qty_producing,
                        "product_raf_id": mrp.product_id.id,
                        "cost_price_foh": foh_cost.amount,
                    }
                )

        if not vals_list:
            raise UserError(
                _(
                    "No matching FOH Item Cost Price data found for the "
                    "given productions. Please run 'FOH Item Cost Price' first."
                )
            )

        # ─────────────────────────────────────────────────────────────
        # STEP 4a: Duplicate validation
        # ─────────────────────────────────────────────────────────────
        duplicates = []
        for v in vals_list:
            existing = self.env["az.foh.production.cost"].search([
                ("trans_date", "=", v["trans_date"]),
                ("mrp_production_id", "=", v["mrp_production_id"]),
                ("product_id_foh", "=", v["product_id_foh"]),
            ], limit=1)
            if existing:
                mrp_name = self.env["mrp.production"].browse(v["mrp_production_id"]).name
                duplicates.append(f"  • {mrp_name} / {v['trans_date']}")

        if duplicates:
            raise ValidationError(
                _("The following records already exist. Please delete them first or use a different period:\n%s")
                % "\n".join(duplicates)
            )

        new_records = self.env["az.foh.production.cost"].create(vals_list)

        # ─────────────────────────────────────────────────────────────
        # STEP 4: Recalculate finished good cost price
        # ─────────────────────────────────────────────────────────────
        new_records.recalculate_cost_fg()

        return {
            "type": "ir.actions.act_window",
            "name": _("FOH Production Cost"),
            "res_model": "az.foh.production.cost",
            "view_mode": "list,form",
            "target": "current",
        }

    def remove_mrp_inventory_data_wizard(self):
        """Wizard method to call remove_mrp_inventory_data from FOH Production Cost model."""
        self.ensure_one()

        # Check if user is administrator (account manager group)
        if not self.env.user.has_group("account.group_account_manager"):
            raise UserError(_("Only administrators can remove MRP and Inventory data."))

        # Call the removal method
        return self.env["az.foh.production.cost"].remove_mrp_inventory_data()
