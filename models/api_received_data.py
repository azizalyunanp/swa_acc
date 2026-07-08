from odoo import models, fields


class SwaApiReceivedData(models.Model):
    _name = 'swa.api.received.data'
    _description = 'API Received Data'

    is_executed = fields.Selection([
        ('No', 'No'),
        ('Yes', 'Yes')
    ], string='Is Executed', default='No')

    data_trans = fields.Text(string='Data Trans')
    type_trans = fields.Char(string='Type Trans', required=True)
    session = fields.Char(string='Session', required=True)

    _sql_constraints = ['unique_session_type', 'unique(session, type_trans)', 'Combination of session and type_trans must be unique']
