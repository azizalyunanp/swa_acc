from odoo import models, fields


class SwaCustInvoiceTransStaging(models.Model):
    _name = 'swa.cust.invoice.trans.staging'
    _description = 'Customer Invoice Transaction Staging (AX 2012)'

    invoice_id = fields.Char(string='Invoice ID')
    invoice_date = fields.Date(string='Invoice Date')
    tax_group = fields.Char(string='Tax Group')
    tax_item_group = fields.Char(string='Tax Item Group')
    purch_price = fields.Float(string='Purchase Price')
    line_amount = fields.Float(string='Line Amount')
    line_amount_mst = fields.Float(string='Line Amount (MST)')
    tax_amount = fields.Float(string='Tax Amount')
    is_executed = fields.Selection([
        ('No', 'No'),
        ('Yes', 'Yes')
    ], string='Is Executed', default='No')
    jour_id = fields.Many2one(
        'swa.cust.invoice.jour.staging',
        string='Invoice Journal')
