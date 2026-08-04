from odoo import models, fields, api


class ProdJournalBomStaging(models.Model):
    _name = 'swa.prod.journal.bom.staging'
    _description = 'Production Journal BOM Staging (AX 2012)'

    orig_rec_id = fields.Char(string='Orig Rec ID')
    prod_id = fields.Char(string='Production ID')
    item_id = fields.Char(string='Item ID')
    unit = fields.Char(string='Unit')
    qty = fields.Float(string='Qty')
    lot = fields.Char(string='Lot')
    site = fields.Char(string='Site')
    warehouse = fields.Char(string='Warehouse')
    is_executed = fields.Selection([
        ('No', 'No'),
        ('Yes', 'Yes')
    ], string='Is Executed', default='No')
    log = fields.Text(string='Log')
    table_id = fields.Many2one(
        'swa.prod.table.staging',
        string='Production Table')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('prod_id') and not vals.get('table_id'):
                parent = self.env['swa.prod.table.staging'].sudo().search([
                    ('prod_id', '=', vals['prod_id']),
                ], limit=1)
                if parent:
                    vals['table_id'] = parent.id
        return super().create(vals_list)
