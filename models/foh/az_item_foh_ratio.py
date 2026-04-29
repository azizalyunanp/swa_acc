# -*- coding: utf-8 -*-

from odoo import models, fields


class AzItemFohRatio(models.Model):
    _name = 'az.item.foh.ratio'
    _description = 'FOH Item Ratio'
    _rec_name = 'product_id'

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
    type = fields.Selection(
        selection=[
            ('none', 'None'),
            ('ratio', 'Ratio'),
            ('gramasi', 'Gramasi'),
            ('squarepic', 'Squarepic'),
            ('swp', 'SWP'),
        ],
        string='Type',
        required=True,
        default='none',
    )
    ratio = fields.Float(
        string='Ratio',
        digits=(16, 4),
        default=0.0,
    )
