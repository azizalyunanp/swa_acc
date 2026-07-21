from odoo import models, fields
import json
import re
import logging

_logger = logging.getLogger(__name__)


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

    _sql_constraints = [('unique_session_type', 'unique(session, type_trans)', 'Combination of session and type_trans must be unique')]

    def _to_snake_case(self, key):
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', key)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def _filter_vals(self, model_name, vals):
        valid_fields = set(self.env[model_name].sudo()._fields.keys())
        return {k: v for k, v in vals.items() if k in valid_fields}

    def _parse_date(self, value):
        if isinstance(value, str) and '/' in value:
            parts = value.split('/')
            if len(parts) == 3:
                return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
        return value

    def action_process_staging(self):
        records = self.search([('is_executed', '=', 'No')])
        _logger.info(f"Cron: found {len(records)} record(s) to process")
        total_created = 0

        for record in records:
            try:
                with self.env.cr.savepoint():
                    json_data = record.data_trans
                    _logger.info(f"Processing record {record.id}: type_trans={record.type_trans}, data_trans_type={type(json_data).__name__}")

                    if isinstance(json_data, str):
                        json_data = json.loads(json_data)

                    if not isinstance(json_data, list):
                        json_data = [json_data]

                    for item in json_data:
                        if not isinstance(item, dict):
                            _logger.warning(f"Record {record.id}: item is not a dict, skipping: {type(item).__name__}")
                            continue

                        vals = {self._to_snake_case(k): v for k, v in item.items()}
                        for date_field in ('invoice_date', 'trans_date'):
                            if date_field in vals:
                                vals[date_field] = self._parse_date(vals[date_field])

                        item_invoice_date = self._parse_date(item.get('InvoiceDate'))
                        item_trans_date = self._parse_date(item.get('TransDate'))

                        if record.type_trans in ('Item', 'InventTable'):
                            existing = self.env['swa.item.staging'].sudo().search_count([
                                ('item_id', '=', item.get('ItemId'))
                            ])
                            if existing == 0:
                                self.env['swa.item.staging'].sudo().create(self._filter_vals('swa.item.staging', vals))
                                total_created += 1
                            else:
                                _logger.info(f"Record {record.id}: Item {item.get('ItemId')} already exists, skipping")

                        elif record.type_trans == 'CustVend':
                            existing = self.env['swa.cust.vend.staging'].sudo().search_count([
                                ('cust_vend_id', '=', item.get('CustVendId'))
                            ])
                            if existing == 0:
                                self.env['swa.cust.vend.staging'].sudo().create(self._filter_vals('swa.cust.vend.staging', vals))
                                total_created += 1
                            else:
                                _logger.info(f"Record {record.id}: CustVend {item.get('CustVendId')} already exists, skipping")

                        elif record.type_trans in ('InventTrans', 'ALL'):
                            existing = self.env['swa.invent.trans.staging'].sudo().search_count([
                                ('orig_rec_id', '=', item.get('OrigRecId'))
                            ])
                            if existing == 0:
                                self.env['swa.invent.trans.staging'].sudo().create(self._filter_vals('swa.invent.trans.staging', vals))
                                total_created += 1
                            else:
                                _logger.info(f"Record {record.id}: InventTrans {item.get('OrigRecId')} already exists, skipping")

                        elif record.type_trans == 'CustInvoiceJour':
                            existing = self.env['swa.cust.invoice.jour.staging'].sudo().search_count([
                                ('invoice_id', '=', item.get('InvoiceId')),
                                ('invoice_date', '=', item_invoice_date)
                            ])
                            if existing == 0:
                                self.env['swa.cust.invoice.jour.staging'].sudo().create(self._filter_vals('swa.cust.invoice.jour.staging', vals))
                                total_created += 1
                            else:
                                _logger.info(f"Record {record.id}: CustInvoiceJour {item.get('InvoiceId')} already exists, skipping")

                        elif record.type_trans == 'CustInvoiceTrans':
                            jour = self.env['swa.cust.invoice.jour.staging'].sudo().search([
                                ('invoice_id', '=', item.get('InvoiceId')),
                                ('invoice_date', '=', item_invoice_date)
                            ], limit=1)
                            if jour:
                                vals['jour_id'] = jour.id
                            vals = self._filter_vals('swa.cust.invoice.trans.staging', vals)
                            existing = self.env['swa.cust.invoice.trans.staging'].sudo().search_count([
                                ('invoice_id', '=', item.get('InvoiceId')),
                                ('invoice_date', '=', item_invoice_date),
                                ('purch_price', '=', item.get('PurchPrice')),
                                ('line_amount', '=', item.get('LineAmount')),
                            ])
                            if existing == 0:
                                self.env['swa.cust.invoice.trans.staging'].sudo().create(vals)
                                total_created += 1
                            else:
                                _logger.info(f"Record {record.id}: CustInvoiceTrans already exists, skipping")

                        elif record.type_trans == 'SalesTable':
                            existing = self.env['swa.sales.table.staging'].sudo().search_count([
                                ('sales_id', '=', item.get('SalesId'))
                            ])
                            if existing == 0:
                                self.env['swa.sales.table.staging'].sudo().create(self._filter_vals('swa.sales.table.staging', vals))
                                total_created += 1
                            else:
                                _logger.info(f"Record {record.id}: SalesTable {item.get('SalesId')} already exists, skipping")

                        elif record.type_trans == 'SalesLine':
                            table = self.env['swa.sales.table.staging'].sudo().search([
                                ('sales_id', '=', item.get('SalesId'))
                            ], limit=1)
                            if table:
                                vals['table_id'] = table.id
                            vals = self._filter_vals('swa.sales.line.staging', vals)
                            existing = self.env['swa.sales.line.staging'].sudo().search_count([
                                ('sales_id', '=', item.get('SalesId')),
                                ('line_num', '=', item.get('LineNum')),
                            ])
                            if existing == 0:
                                self.env['swa.sales.line.staging'].sudo().create(vals)
                                total_created += 1
                            else:
                                _logger.info(f"Record {record.id}: SalesLine already exists, skipping")

                        elif record.type_trans == 'VendInvoiceJour':
                            existing = self.env['swa.vend.invoice.jour.staging'].sudo().search_count([
                                ('invoice_id', '=', item.get('InvoiceId')),
                                ('invoice_date', '=', item.get('InvoiceDate'))
                            ])
                            if existing == 0:
                                self.env['swa.vend.invoice.jour.staging'].sudo().create(self._filter_vals('swa.vend.invoice.jour.staging', vals))
                                total_created += 1
                            else:
                                _logger.info(f"Record {record.id}: VendInvoiceJour {item.get('InvoiceId')} already exists, skipping")

                        elif record.type_trans == 'VendInvoiceTrans':
                            jour = self.env['swa.vend.invoice.jour.staging'].sudo().search([
                                ('invoice_id', '=', item.get('InvoiceId')),
                                ('invoice_date', '=', item.get('InvoiceDate'))
                            ], limit=1)
                            if jour:
                                vals['jour_id'] = jour.id
                            vals = self._filter_vals('swa.vend.invoice.trans.staging', vals)
                            existing = self.env['swa.vend.invoice.trans.staging'].sudo().search_count([
                                ('invoice_id', '=', item.get('InvoiceId')),
                                ('invoice_date', '=', item.get('InvoiceDate')),
                                ('line_amount', '=', item.get('LineAmount')),
                            ])
                            if existing == 0:
                                self.env['swa.vend.invoice.trans.staging'].sudo().create(vals)
                                total_created += 1
                            else:
                                _logger.info(f"Record {record.id}: VendInvoiceTrans already exists, skipping")

                        elif record.type_trans == 'PurchTable':
                            existing = self.env['swa.purch.table.staging'].sudo().search_count([
                                ('purch_id', '=', item.get('PurchId'))
                            ])
                            if existing == 0:
                                self.env['swa.purch.table.staging'].sudo().create(self._filter_vals('swa.purch.table.staging', vals))
                                total_created += 1
                            else:
                                _logger.info(f"Record {record.id}: PurchTable {item.get('PurchId')} already exists, skipping")

                        elif record.type_trans == 'PurchLine':
                            table = self.env['swa.purch.table.staging'].sudo().search([
                                ('purch_id', '=', item.get('PurchId'))
                            ], limit=1)
                            if table:
                                vals['table_id'] = table.id
                            vals = self._filter_vals('swa.purch.line.staging', vals)
                            existing = self.env['swa.purch.line.staging'].sudo().search_count([
                                ('purch_id', '=', item.get('PurchId')),
                                ('item_id', '=', item.get('ItemId')),
                            ])
                            if existing == 0:
                                self.env['swa.purch.line.staging'].sudo().create(vals)
                                total_created += 1
                            else:
                                _logger.info(f"Record {record.id}: PurchLine already exists, skipping")

                        else:
                            _logger.warning(f"Record {record.id}: Unknown type_trans '{record.type_trans}', skipping")

                    record.sudo().write({'is_executed': 'Yes'})

            except Exception as e:
                _logger.error(f"Cron error processing record {record.id}: {str(e)}")
                _logger.error(f"Exception type: {type(e).__name__}")

        _logger.info(f"Cron: finished. Total staging records created: {total_created}")
        return True

    def action_auto_migrate(self):
        _logger.info("Auto-migrate: started")

        # 1. Process products from ItemStaging
        items = self.env['swa.item.staging'].sudo().search([('is_executed', '=', 'No')])
        items.action_create_product()
        _logger.info(f"Auto-migrate: processed {len(items)} item(s)")

        # 2. Process partners from CustVendStaging
        partners = self.env['swa.cust.vend.staging'].sudo().search([('is_executed', '=', 'No')])
        partners.action_create_partner()
        _logger.info(f"Auto-migrate: processed {len(partners)} partner(s)")

        # 3. Process sale orders from SalesTableStaging
        sales = self.env['swa.sales.table.staging'].sudo().search([('is_executed', '=', 'No')])
        sales.action_create_sale_order()
        _logger.info(f"Auto-migrate: processed {len(sales)} sale order(s)")

        # 4. Process purchase orders from PurchTableStaging
        purchases = self.env['swa.purch.table.staging'].sudo().search([('is_executed', '=', 'No')])
        purchases.action_create_purchase_order()
        _logger.info(f"Auto-migrate: processed {len(purchases)} purchase order(s)")

        _logger.info("Auto-migrate: finished")
        return True
