from odoo import models, fields


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    swa_receipt_reference = fields.Char(string='Receipt Reference')
