from odoo import models, fields

class ProductCategory(models.Model):
    _inherit = 'product.category'

    az_property_raf_account_id = fields.Many2one(
        'account.account', 
        string="Report as Finished Account",
        company_dependent=True,
        help="Account used for Report as Finished (RAF) journal entries."
    )
    az_property_raw_material_account_id = fields.Many2one(
        'account.account', 
        string="Raw Material Account",
        company_dependent=True,
        help="Account used for Raw Material picking journal entries."
    )
    az_property_wip_account_id = fields.Many2one(
        'account.account', 
        string="WIP Account",
        company_dependent=True,
        help="Work in Progress (WIP) Account."
    )
