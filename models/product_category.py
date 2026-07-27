from odoo import models, fields


class ProductCategory(models.Model):
    _inherit = 'product.category'

    swa_short_code = fields.Char(string='SWA Short Code')
