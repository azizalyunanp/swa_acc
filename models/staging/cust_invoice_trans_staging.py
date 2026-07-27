from odoo import models, fields, api


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
    invent_site_id = fields.Char(string='Invent Site ID')
    invent_location_id = fields.Char(string='Invent Location ID')
    qty = fields.Float(string='Qty')
    item_id = fields.Char(string='Item ID')
    lot = fields.Char(string='Lot')
    harga_penyerahan = fields.Float(string='Harga Penyerahan')
    orig_sales_id = fields.Char(string='Orig Sales ID')
    is_executed = fields.Selection([
        ('No', 'No'),
        ('Yes', 'Yes')
    ], string='Is Executed', default='No')
    log = fields.Text(string='Log')
    jour_id = fields.Many2one(
        'swa.cust.invoice.jour.staging',
        string='Invoice Journal')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('invoice_id') and not vals.get('jour_id'):
                jour = self.env['swa.cust.invoice.jour.staging'].sudo().search([
                    ('invoice_id', '=', vals['invoice_id']),
                ], limit=1)
                if jour:
                    vals['jour_id'] = jour.id
        return super().create(vals_list)
