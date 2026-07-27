from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


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
    log = fields.Text(string='Log')

    def action_create_partner(self):
        for rec in self:
            try:
                with self.env.cr.savepoint():
                    domain = [('ref', '=', rec.cust_vend_id)]
                    if rec.type_cust_vend == 'Customer':
                        domain.append(('customer_rank', '>', 0))
                    elif rec.type_cust_vend == 'Vendor':
                        domain.append(('supplier_rank', '>', 0))

                    existing = self.env['res.partner'].sudo().search(domain, limit=1)
                    if existing:
                        rec.write({
                            'is_executed': 'Yes',
                            'log': f"Skipped: Partner with ref '{rec.cust_vend_id}' already exists (ID: {existing.id})"
                        })
                        continue

                    vals = {
                        'ref': rec.cust_vend_id,
                        'name': rec.name or rec.cust_vend_id,
                        'street': rec.address,
                        'street2': rec.address_ext,
                    }
                    if rec.type_cust_vend == 'Customer':
                        vals['customer_rank'] = 1
                    elif rec.type_cust_vend == 'Vendor':
                        vals['supplier_rank'] = 1

                    partner = self.env['res.partner'].sudo().create(vals)
                    rec.write({
                        'is_executed': 'Yes',
                        'log': f"Success: Partner created (ID: {partner.id}, Name: {partner.name})"
                    })

            except Exception as e:
                rec.write({'log': f"Error: {str(e)}"})
                _logger.error(f"CustVendStaging {rec.id} action_create_partner error: {str(e)}")
