# -*- coding: utf-8 -*-

from odoo import models, fields


class AzMappingAccountFoh(models.Model):
    _name = 'az.mapping.account.foh'
    _description = 'FOH Mapping Account'
    _rec_name = 'account_id'

    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Account',
        required=True,
        ondelete='restrict',
    )
    account_name = fields.Char(
        string='Account Name',
        related='account_id.name',
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
