from odoo import models, fields


class SwaStagingSetup(models.Model):
    _name = 'swa.staging.setup'
    _description = 'Staging Setup - Site to Company Mapping'

    name = fields.Char(string='Name')
    invent_site_id = fields.Char(string='Invent Site ID', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True)
    active = fields.Boolean(string='Active', default=True)

    def action_fix_chart_template(self):
        company = self.env['res.company'].sudo().search([], limit=1)
        if not company:
            return self._notification('Error', 'No company found.', 'danger')
 
        company.sudo().write({'chart_template': 'id'})
        return self._notification('Success', 'chart_template set to "id" (Indonesia). Reload page.', 'success')

    def _notification(self, title, message, msg_type='info'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'sticky': False, 'type': msg_type},
        }
