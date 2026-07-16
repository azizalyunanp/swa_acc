from odoo import models, fields


class SwaCustInvoiceJourStaging(models.Model):
    _name = 'swa.cust.invoice.jour.staging'
    _description = 'Customer Invoice Journal Staging (AX 2012)'

    invoice_id = fields.Char(string='Invoice ID')
    invoice_account = fields.Char(string='Invoice Account')
    incl_tax = fields.Char(string='Include Tax')
    currency = fields.Char(string='Currency')
    invoice_date = fields.Date(string='Invoice Date')
    tax_group = fields.Char(string='Tax Group')
    invoice_amount = fields.Float(string='Invoice Amount')
    invoice_amount_mst = fields.Float(string='Invoice Amount (MST)')
    tax_amount = fields.Float(string='Tax Amount')
    is_executed = fields.Selection([
        ('No', 'No'),
        ('Yes', 'Yes')
    ], string='Is Executed', default='No')
    line_ids = fields.One2many(
        'swa.cust.invoice.trans.staging', 'jour_id',
        string='Invoice Lines')
