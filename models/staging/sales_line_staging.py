from odoo import models, fields


class SwaSalesLineStaging(models.Model):
    _name = 'swa.sales.line.staging'
    _description = 'Sales Line Staging (AX 2012)'

    sales_id = fields.Char(string='Sales ID')
    cust_account = fields.Char(string='Cust Account')
    currency_code = fields.Char(string='Currency Code')
    item_id = fields.Char(string='Item ID')
    dlv_mode = fields.Char(string='Dlv Mode')
    dlv_term = fields.Char(string='Dlv Term')
    sales_price = fields.Float(string='Sales Price')
    sales_qty = fields.Float(string='Sales Qty')
    sales_unit = fields.Char(string='Sales Unit')
    external_item_id = fields.Char(string='External Item ID')
    external_item_desc = fields.Char(string='External Item Desc')
    invent_dim_id = fields.Char(string='Invent Dim ID')
    tax_item_group = fields.Char(string='Tax Item Group')
    tax_group = fields.Char(string='Tax Group')
    line_disc = fields.Float(string='Line Disc')
    line_percent = fields.Float(string='Line Percent')
    price_unit = fields.Float(string='Price Unit')
    line_num = fields.Float(string='Line Num')
    is_executed = fields.Selection([
        ('No', 'No'),
        ('Yes', 'Yes')
    ], string='Is Executed', default='No')
    log = fields.Text(string='Log')
    table_id = fields.Many2one(
        'swa.sales.table.staging',
        string='Sales Table')
