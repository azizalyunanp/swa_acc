from odoo import models, fields


class SwaItemStaging(models.Model):
    _name = 'swa.item.staging'
    _description = 'Item Staging (AX 2012)'

    item_id = fields.Char(string='Item ID')
    item_name = fields.Char(string='Item Name')
    unit_id = fields.Char(string='Unit ID')
    type_item = fields.Char(string='Type Item')
    is_executed = fields.Selection([
        ('No', 'No'),
        ('Yes', 'Yes')
    ], string='Is Executed', default='No')
