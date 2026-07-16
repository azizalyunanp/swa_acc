from odoo import models, fields


class SwaCustVendStaging(models.Model):
    _name = 'swa.cust.vend.staging'
    _description = 'Customer/Vendor Staging (AX 2012)'

    cust_vend_id = fields.Char(string='Customer/Vendor ID')
    name = fields.Char(string='Name')
    address = fields.Text(string='Address')
    address_ext = fields.Text(string='Address Ext')
    type_cust_vend = fields.Selection([
        ('Customer', 'Customer'),
        ('Vendor', 'Vendor')
    ], string='Type')
    is_executed = fields.Selection([
        ('No', 'No'),
        ('Yes', 'Yes')
    ], string='Is Executed', default='No')
