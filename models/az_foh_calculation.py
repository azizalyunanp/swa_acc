# -*- coding: utf-8 -*-

from odoo import models, fields


class AzFohCalculation(models.Model):
    _name = 'az.foh.calculation'
    _description = 'FOH Calculation'
    _rec_name = 'product_id'
    _order = 'trans_date desc, product_id'

    trans_date = fields.Date(
        string='Trans Date',
    )
    location_id = fields.Many2one(
        comodel_name='stock.location',
        string='Location',
        domain=[('usage', '=', 'internal')],
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        required=True,
        ondelete='restrict',
    )
    product_name = fields.Char(
        string='Product Name',
        related='product_id.name',
        readonly=True,
    )
    qty_raf = fields.Float(
        string='Qty RAF',
        digits=(16, 4),
        default=0.0,
    )
    uom = fields.Many2one(
        comodel_name='uom.uom',
        string='UOM',
    )
    qty_raf_convert = fields.Float(
        string='Qty RAF Convert',
        digits=(16, 4),
        default=0.0,
    )
    uom_convert = fields.Many2one(
        comodel_name='uom.uom',
        string='UOM Convert',
    )
    ratio = fields.Float(
        string='Ratio',
        digits=(16, 4),
        default=0.0,
    )
    prod_equ = fields.Float(
        string='Prod. Equ.',
        digits=(16, 4),
        default=0.0,
    )
    prod_equ_weight = fields.Float(
        string='Prod. Equ. Weight',
        digits=(16, 4),
        default=0.0,
    )

    # Electricity
    percent_electricity = fields.Float(
        string='% Electricity',
        digits=(16, 4),
        default=0.0,
    )
    amount_electricity = fields.Float(
        string='Amount Electricity',
        digits=(16, 2),
        default=0.0,
    )

    # Wage
    percent_wage = fields.Float(
        string='% Wage',
        digits=(16, 4),
        default=0.0,
    )
    amount_wage = fields.Float(
        string='Amount Wage',
        digits=(16, 2),
        default=0.0,
    )

    # Overtime
    percent_overtime = fields.Float(
        string='% Overtime',
        digits=(16, 4),
        default=0.0,
    )
    amount_overtime = fields.Float(
        string='Amount Overtime',
        digits=(16, 2),
        default=0.0,
    )

    # Others
    percent_others = fields.Float(
        string='% Others',
        digits=(16, 4),
        default=0.0,
    )
    amount_others = fields.Float(
        string='Amount Others',
        digits=(16, 2),
        default=0.0,
    )

    # Sparepart
    percent_sparepart = fields.Float(
        string='% Sparepart',
        digits=(16, 4),
        default=0.0,
    )
    amount_sparepart = fields.Float(
        string='Amount Sparepart',
        digits=(16, 2),
        default=0.0,
    )

    # Fuel
    percent_fuel = fields.Float(
        string='% Fuel',
        digits=(16, 4),
        default=0.0,
    )
    amount_fuel = fields.Float(
        string='Amount Fuel',
        digits=(16, 2),
        default=0.0,
    )

    # Depreciation
    percent_depreciation = fields.Float(
        string='% Depreciation',
        digits=(16, 4),
        default=0.0,
    )
    amount_depreciation = fields.Float(
        string='Amount Depreciation',
        digits=(16, 2),
        default=0.0,
    )

    # Work Order
    percent_workorder = fields.Float(
        string='% Work Order',
        digits=(16, 4),
        default=0.0,
    )
    amount_workorder = fields.Float(
        string='Amount Work Order',
        digits=(16, 2),
        default=0.0,
    )

    # Packing
    percent_packing = fields.Float(
        string='% Packing',
        digits=(16, 4),
        default=0.0,
    )
    amount_packing = fields.Float(
        string='Amount Packing',
        digits=(16, 2),
        default=0.0,
    )
