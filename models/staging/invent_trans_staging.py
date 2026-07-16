from odoo import models, fields


class SwaInventTransStaging(models.Model):
    _name = 'swa.invent.trans.staging'
    _description = 'Inventory Transaction Staging (AX 2012)'

    orig_rec_id = fields.Char(string='Orig Rec ID')
    no_aju = fields.Char(string='No Aju')
    bc_type = fields.Char(string='BC Type')
    bc_no = fields.Char(string='BC No')
    bc_date = fields.Char(string='BC Date')
    invoice_id = fields.Char(string='Invoice ID')
    trans_no = fields.Char(string='Trans No')
    netto = fields.Float(string='Netto')
    item_id = fields.Char(string='Item ID')
    inventserial = fields.Char(string='Invent Serial')
    site = fields.Char(string='Site')
    warehouse = fields.Char(string='Warehouse')
    warehouse_type = fields.Char(string='Warehouse Type')
    location = fields.Char(string='Location')
    invent_batch_id = fields.Char(string='Invent Batch ID')
    transtype = fields.Char(string='Trans Type')
    modified_by = fields.Char(string='Modified By')
    modified_date_time = fields.Char(string='Modified Date/Time')
    cust_vend_id = fields.Char(string='Customer/Vendor ID')
    doc_no = fields.Char(string='Doc No')
    doc_date = fields.Char(string='Doc Date')
    no_faktur_pajak = fields.Char(string='No Faktur Pajak')
    qty = fields.Float(string='Qty')
    trans_date = fields.Date(string='Trans Date')
    trans_unit = fields.Char(string='Trans Unit')
    trans_qty = fields.Float(string='Trans Qty')
    journal_inv_type = fields.Char(string='Journal Inv Type')
    invent_ref_id = fields.Char(string='Invent Ref ID')
    currency = fields.Char(string='Currency')
    cost_price = fields.Float(string='Cost Price')
    cost_amount = fields.Float(string='Cost Amount')
    packing_slip_id = fields.Char(string='Packing Slip ID')
    peb = fields.Char(string='PEB')
    is_executed = fields.Selection([
        ('No', 'No'),
        ('Yes', 'Yes')
    ], string='Is Executed', default='No')
