# -*- coding: utf-8 -*-

from odoo import models, fields


class AzMappingItemFoh(models.Model):
    _name = 'az.mapping.item.foh'
    _description = 'FOH Mapping Item'
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
    type = fields.Selection(
        selection=[
            ('none', 'None'),
            ('electricity', 'Electricity'),
            ('wage', 'Wage'),
            ('overtime', 'Overtime'),
            ('others', 'Others'),
            ('sparepart', 'Sparepart'),
            ('fuel', 'Fuel'),
            ('depreciation', 'Depreciation'),
            ('work_order', 'WorkOrder'),
            ('packing', 'Packing'),
        ],
        string='Type',
        required=True,
        default='none',
    )
