from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    az_calculate_raf_pick_account_automate = fields.Boolean(
        string="Calculate RAF & Pick Account Automate when Produce",
        config_parameter='swa_acc.az_calculate_raf_pick_account_automate'
    )
