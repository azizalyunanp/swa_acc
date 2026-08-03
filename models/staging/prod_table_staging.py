from odoo import models, fields


class ProdTableStaging(models.Model):
    _name = 'swa.prod.table.staging'
    _description = 'Production Table Staging (AX 2012)'

    orig_rec_id = fields.Char(string='Orig Rec ID')
    prod_id = fields.Char(string='Production ID')
    item_id = fields.Char(string='Item ID')
    nomor_wo = fields.Char(string='Nomor WO')
    qty = fields.Float(string='Qty')
    invent_ref_id = fields.Char(string='Invent Ref ID')
    prod_pool = fields.Char(string='Prod Pool')
    site = fields.Char(string='Site')
    warehouse = fields.Char(string='Warehouse')
    is_executed = fields.Selection([
        ('No', 'No'),
        ('Yes', 'Yes')
    ], string='Is Executed', default='No')
    log = fields.Text(string='Log')
    line_ids_bom = fields.One2many(
        'swa.prod.journal.bom.staging', 'table_id',
        string='BOM Lines')
    line_ids_prod = fields.One2many(
        'swa.prod.journal.prod.staging', 'table_id',
        string='Production Lines')