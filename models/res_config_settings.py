from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    az_calculate_raf_pick_account_automate = fields.Boolean(string="Calculate RAF & Pick Account Automate when Produce")

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    az_calculate_raf_pick_account_automate = fields.Boolean(
        related='company_id.az_calculate_raf_pick_account_automate',
        readonly=False,
        string="Calculate RAF & Pick Account Automate when Produce"
    )
