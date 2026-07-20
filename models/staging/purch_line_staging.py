from odoo import models, fields


class SwaPurchLineStaging(models.Model):
    _name = 'swa.purch.line.staging'
    _description = 'Purchase Line Staging (AX 2012)'

    purch_id = fields.Char(string='Purchase ID')
    item_id = fields.Char(string='Item ID')
    invent_dim_id = fields.Char(string='Invent Dim ID')
    remain_invent_physical = fields.Float(string='Remain Invent Physical')
    purch_price = fields.Float(string='Purchase Price')
    tax_item_group = fields.Char(string='Tax Item Group')
    tax_group = fields.Char(string='Tax Group')
    line_disc = fields.Float(string='Line Disc')
    line_percent = fields.Float(string='Line Percent')
    delivery_date = fields.Char(string='Delivery Date')
    purch_unit = fields.Char(string='Purch Unit')
    remain_purch_physical = fields.Float(string='Remain Purch Physical')
    purch_qty = fields.Float(string='Purch Qty')
    # data_area_id = fields.Char(string='Data Area ID')
    is_executed = fields.Selection([
        ('No', 'No'),
        ('Yes', 'Yes')
    ], string='Is Executed', default='No')
    log = fields.Text(string='Log')
    table_id = fields.Many2one(
        'swa.purch.table.staging',
        string='Purchase Table')
