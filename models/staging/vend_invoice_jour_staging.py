from odoo import models, fields


class SwaVendInvoiceJourStaging(models.Model):
    _name = 'swa.vend.invoice.jour.staging'
    _description = 'Vendor Invoice Journal Staging (AX 2012)'

    invoice_id = fields.Char(string='Invoice ID')
    invoice_account = fields.Char(string='Invoice Account')
    incl_tax = fields.Char(string='Include Tax')
    internal_packing_slip = fields.Char(string='Internal Packing Slip')
    currency = fields.Char(string='Currency')
    invoice_date = fields.Char(string='Invoice Date')
    tax_group = fields.Char(string='Tax Group')
    invoice_amount = fields.Float(string='Invoice Amount')
    invoice_amount_mst = fields.Float(string='Invoice Amount (MST)')
    tax_amount = fields.Float(string='Tax Amount')
    is_executed = fields.Selection([
        ('No', 'No'),
        ('Yes', 'Yes')
    ], string='Is Executed', default='No')
    log = fields.Text(string='Log')
    line_ids = fields.One2many(
        'swa.vend.invoice.trans.staging', 'jour_id',
        string='Invoice Lines')
