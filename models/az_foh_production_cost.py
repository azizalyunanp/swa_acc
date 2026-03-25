# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AzFohProductionCost(models.Model):
    _name = "az.foh.production.cost"
    _description = "FOH Production Cost"
    _rec_name = "mrp_production_id"
    _order = "trans_date desc, mrp_production_id"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    trans_date = fields.Date(
        string="Trans Date",
    )
    location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Location",
        domain=[("usage", "=", "internal")],
    )
    mrp_production_id = fields.Many2one(
        comodel_name="mrp.production",
        string="Production Order",
        ondelete="restrict",
    )
    lot_id = fields.Many2one(
        comodel_name="stock.lot",
        string="Lot/Serial",
        ondelete="restrict",
    )
    product_id_foh = fields.Many2one(
        comodel_name="product.product",
        string="FOH Item",
        ondelete="restrict",
    )
    product_foh_default_code = fields.Char(
        string="FOH Item Code",
        related="product_id_foh.default_code",
        readonly=True,
    )
    product_name_foh = fields.Char(
        string="FOH Item Name",
        related="product_id_foh.name",
        readonly=True,
    )
    product_foh_qty = fields.Float(
        string="FOH Qty",
        digits=(16, 4),
        default=0.0,
    )
    product_raf_id = fields.Many2one(
        comodel_name="product.product",
        string="RAF Product",
        ondelete="restrict",
    )
    product_raf_default_code = fields.Char(
        string="RAF Product Code",
        related="product_raf_id.default_code",
        readonly=True,
    )
    product_raf_name = fields.Char(
        string="RAF Product Name",
        related="product_raf_id.name",
        readonly=True,
    )
    cost_price_foh = fields.Float(
        string="Cost Price FOH",
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

        Writes results to az_foh_production_price (rm_cost, foh_cost, total_cost).
        Use the Calculate Average Product button in az_foh_production_price view
        to then aggregate into az_foh_cost_price_fg.
        """
        productions = self.mapped("mrp_production_id")

        if not productions:
            raise UserError(_("No Production Order linked to the selected records."))

        # Delegate to az_foh_production_price model
        self.env["az.foh.production.price"].generate_from_productions(productions)

        return True

    def remove_mrp_inventory_data(self):
        """
        Remove MRP and Inventory data using SQL for clean reset.
        This will delete:
        - az_foh_cost_price_fg
        - az_foh_production_price
        - az_foh_production_cost
        - mrp.production and related records
        - stock.picking, stock.move, stock.move.line
        - stock.quant (for internal locations)
        """
        import logging

        _logger = logging.getLogger(__name__)

        try:
            # Disable foreign key checks temporarily
            self._cr.execute("SET CONSTRAINTS ALL DEFERRED")

            # 1. Delete FOH related data first (order matters: child → parent)
            _logger.info("Deleting az_foh_cost_price_fg...")
            self._cr.execute("DELETE FROM az_foh_cost_price_fg")

            _logger.info("Deleting az_foh_production_price...")
            self._cr.execute("DELETE FROM az_foh_production_price")

            _logger.info("Deleting az_foh_production_cost...")
            self._cr.execute("DELETE FROM az_foh_production_cost")

            _logger.info("Deleting az_foh_item_cost_price...")
            self._cr.execute("DELETE FROM az_foh_item_cost_price")

            _logger.info("Deleting az_foh_calculation...")
            self._cr.execute("DELETE FROM az_foh_calculation")

            # Clean up legacy table if still present in DB
            _logger.info("Deleting az_foh_mrp_cost_price (legacy)...")
            self._cr.execute("""
                DELETE FROM az_foh_mrp_cost_price
                WHERE EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'az_foh_mrp_cost_price'
                )
            """)

            # 2. Delete MRP data (child tables first)
            _logger.info("Deleting mrp.workcenter.productivity...")
            self._cr.execute("DELETE FROM mrp_workcenter_productivity")

            _logger.info("Deleting mrp.workorder...")
            self._cr.execute("DELETE FROM mrp_workorder")

            _logger.info("Deleting stock.move.line (MRP related)...")
            self._cr.execute("""
                DELETE FROM stock_move_line 
                WHERE move_id IN (
                    SELECT sm.id FROM stock_move sm
                    JOIN mrp_production mp ON sm.raw_material_production_id = mp.id 
                    OR sm.production_id = mp.id
                )
            """)

            _logger.info("Deleting stock.move (MRP related)...")
            self._cr.execute("""
                DELETE FROM stock_move 
                WHERE raw_material_production_id IS NOT NULL 
                OR production_id IS NOT NULL
            """)

            _logger.info("Deleting mrp.production...")
            self._cr.execute("DELETE FROM mrp_production")

            # 3. Delete general Inventory data
            _logger.info("Deleting stock.move.line...")
            self._cr.execute("DELETE FROM stock_move_line")

            _logger.info("Deleting stock.move...")
            self._cr.execute("DELETE FROM stock_move")

            _logger.info("Deleting stock.picking...")
            self._cr.execute("DELETE FROM stock_picking")

            _logger.info("Deleting stock.quant (internal locations only)...")
            self._cr.execute("""
                DELETE FROM stock_quant 
                WHERE location_id IN (
                    SELECT id FROM stock_location WHERE usage = 'internal'
                )
            """)

            _logger.info("Deleting stock.valuation.layer...")
            self._cr.execute("DELETE FROM stock_valuation_layer")

            # 4. Reset sequences
            _logger.info("Resetting sequences...")
            self._cr.execute("""
                UPDATE ir_sequence 
                SET number_next = 1 
                WHERE code LIKE 'mrp.%' 
                OR code LIKE 'stock.%'
                OR prefix LIKE 'WH/%'
            """)

            # Commit all changes
            self._cr.commit()

            _logger.info("Successfully removed all MRP and Inventory data!")

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Success"),
                    "message": _(
                        "All MRP and Inventory data has been removed successfully."
                    ),
                    "type": "success",
                    "sticky": False,
                },
            }

        except Exception as e:
            self._cr.rollback()
            _logger.error("Error removing data: %s", str(e))
            raise UserError(_("Error removing data: %s") % str(e))
