# -*- coding: utf-8 -*-

from odoo import models, fields


class AzFohItemCostPrice(models.Model):
    _name = 'az.foh.item.cost.price'
    _description = 'FOH Item Cost Price'
    _rec_name = 'product_id'
    _order = 'trans_date desc, product_id'

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
    default_code = fields.Char(
        string='Product Code',
        related='product_id.default_code',
        readonly=True,
    )
    trans_date = fields.Date(
        string='Trans Date',
    )
    location_id = fields.Many2one(
        comodel_name='stock.location',
        string='Location',
        domain=[('usage', '=', 'internal')],
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
    product_id_foh = fields.Many2one(
        comodel_name='product.product',
        string='FOH Item',
        ondelete='restrict',
    )
    uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string='UOM',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
    )
    amount = fields.Float(
        string='Amount',
        digits=(16, 2),
        default=0.0,
    )
