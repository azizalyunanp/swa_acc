from odoo import models, fields


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    code = fields.Char(
        string='Short Name',
        required=True,
        size=10,
        help="Short name used to identify your warehouse (max 10 characters)"
    )

