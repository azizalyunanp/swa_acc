from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    swa_picking_id = fields.Many2one(
        'stock.picking', string='Receipt Picking')
