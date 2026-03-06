# -*- coding: utf-8 -*-

from odoo import models, fields, _
from odoo.exceptions import UserError


class AzFohProductionCost(models.Model):
    _name = 'az.foh.production.cost'
    _description = 'FOH Production Cost'
    _rec_name = 'mrp_production_id'
    _order = 'trans_date desc, mrp_production_id'

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
    trans_date = fields.Date(
        string='Trans Date',
    )
    location_id = fields.Many2one(
        comodel_name='stock.location',
        string='Location',
        domain=[('usage', '=', 'internal')],
    )
    mrp_production_id = fields.Many2one(
        comodel_name='mrp.production',
        string='Production Order',
        ondelete='restrict',
    )
    product_id_foh = fields.Many2one(
        comodel_name='product.product',
        string='FOH Item',
        ondelete='restrict',
    )
    product_foh_default_code = fields.Char(
        string='FOH Item Code',
        related='product_id_foh.default_code',
        readonly=True,
    )
    product_name_foh = fields.Char(
        string='FOH Item Name',
        related='product_id_foh.name',
        readonly=True,
    )
    product_foh_qty = fields.Float(
        string='FOH Qty',
        digits=(16, 4),
        default=0.0,
    )
    product_raf_id = fields.Many2one(
        comodel_name='product.product',
        string='RAF Product',
        ondelete='restrict',
    )
    product_raf_default_code = fields.Char(
        string='RAF Product Code',
        related='product_raf_id.default_code',
        readonly=True,
    )
    product_raf_name = fields.Char(
        string='RAF Product Name',
        related='product_raf_id.name',
        readonly=True,
    )
    cost_price_foh = fields.Float(
        string='Cost Price FOH',
        digits=(16, 2),
        default=0.0,
    )

    # ──────────────────────────────────────────────────────────────────
    # Business Logic
    # ──────────────────────────────────────────────────────────────────

    def recalculate_cost_fg(self):
        """
        Recalculate the finished good (FG) cost price for each MRP
        linked to the selected FOH Production Cost records.

        Formula:
          total_raw_cost = Σ( move_line.quantity × item_price )
            where item_price = lot.standard_price  (if tracking='lot')
                            OR product.standard_price (if tracking='none')

          total_foh_cost  = Σ( az.foh.production.cost.cost_price_foh )
                            for the same MRP production

          cost_per_unit   = (total_raw_cost + total_foh_cost) / mrp.qty_producing

        Update target:
          tracking='lot'  → weighted average into lot.standard_price
          tracking='none' → weighted average into product.standard_price
        """
        productions = self.mapped('mrp_production_id')

        if not productions:
            raise UserError(_("No Production Order linked to the selected records."))

        for mrp in productions:
            qty_producing = mrp.qty_producing or 0.0
            if qty_producing <= 0:
                continue

            # ── STEP 1: Raw material cost ──────────────────────────────
            total_raw_cost = 0.0
            raw_moves = mrp.move_raw_ids.filtered(lambda m: m.state == 'done')

            for move in raw_moves:
                for ml in move.move_line_ids:
                    qty = ml.quantity
                    if qty <= 0:
                        continue

                    product = ml.product_id
                    if product.tracking == 'lot' and ml.lot_id:
                        # Use lot standard_price if the field exists
                        price = (
                            ml.lot_id.standard_price
                            if hasattr(ml.lot_id, 'standard_price') and ml.lot_id.standard_price
                            else product.standard_price
                        )
                    else:
                        price = product.standard_price

                    total_raw_cost += qty * price

            # ── STEP 2: FOH cost for this MRP ─────────────────────────
            foh_records = self.env['az.foh.production.cost'].search([
                ('mrp_production_id', '=', mrp.id),
            ])
            total_foh_cost = sum(foh_records.mapped('cost_price_foh'))

            # ── STEP 3: Cost per unit ──────────────────────────────────
            total_cost    = total_raw_cost + total_foh_cost
            cost_per_unit = total_cost / qty_producing

            # ── STEP 4: Update finished good price ────────────────────
            fg_product = mrp.product_id

            if fg_product.tracking == 'lot' and mrp.lot_producing_id:
                lot = mrp.lot_producing_id
                lot_qty    = lot.product_qty
                done_qty   = qty_producing if mrp.state == 'done' else 0.0
                prev_qty   = max(lot_qty - done_qty, 0.0)
                total_qty  = prev_qty + qty_producing

                if total_qty > 0:
                    old_price = (
                        lot.standard_price
                        if hasattr(lot, 'standard_price') and lot.standard_price
                        else fg_product.standard_price
                    )
                    new_price = (
                        cost_per_unit
                        if old_price == 0
                        else ((prev_qty * old_price) + (qty_producing * cost_per_unit)) / total_qty
                    )
                    if hasattr(lot, 'standard_price'):
                        lot.sudo().write({'standard_price': new_price})
                    else:
                        fg_product.sudo().write({'standard_price': new_price})

            else:
                # Non-lot: weighted average with current stock
                current_qty = fg_product.qty_available
                done_qty    = qty_producing if mrp.state == 'done' else 0.0
                prev_qty    = max(current_qty - done_qty, 0.0)
                total_qty   = prev_qty + qty_producing

                if total_qty > 0:
                    old_price = fg_product.standard_price
                    new_price = (
                        cost_per_unit
                        if old_price == 0
                        else ((prev_qty * old_price) + (qty_producing * cost_per_unit)) / total_qty
                    )
                    fg_product.sudo().write({'standard_price': new_price})

        return True
