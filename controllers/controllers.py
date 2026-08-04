# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import re
import logging

_logger = logging.getLogger(__name__)


class SynchDataController(http.Controller):

    @http.route('/synchronize_data', type='http', auth="none", methods=['POST'], csrf=False)
    def synch_data(self, **kwargs):
        try:
            _logger.info("Endpoint /synchronize_data dipanggil")

            data = request.jsonrequest
            _logger.info(f"Data diterima: {data}")

            if not data:
                raise ValueError("Data tidak boleh kosong")

            if not data.get('type_trans') or not data.get('session'):
                raise ValueError("type_trans and session are required")

            SwaApiReceivedData = request.env['swa.api.received.data']
            new_data = SwaApiReceivedData.sudo().create({
                'type_trans': data.get('type_trans'),
                'session': data.get('session'),
                'data_trans': json.dumps(data.get('data_trans')) if isinstance(data.get('data_trans'), (dict, list)) else data.get('data_trans'),
                'is_executed': 'No'
            })

            _logger.info(f"Data berhasil disimpan dengan ID: {new_data.id}")

            response = {
                'success': '1',
                'error': '0',
                'message': 'Data berhasil disimpan',
                'record_id': new_data.id
            }

        except Exception as e:
            _logger.error(f"Error pada /synchronize_data: {str(e)}")
            response = {
                'success': '0',
                'error': str(e),
                'message': 'Terjadi kesalahan saat menyimpan data'
            }
            return request.make_json_response(response, status=500)

        return request.make_json_response(response)

    @http.route('/synchronize_data/test', type='http', auth="public", methods=['GET'])
    def test_endpoint(self, **kwargs):
        return "Endpoint synchronize_data berfungsi dengan baik!"




class StagingDataController(http.Controller):

    @http.route('/handle_staging_data', type='http', auth="none", methods=['POST'], csrf=False)
    def handle_staging_data(self, **kwargs):
        try:
            data = request.jsonrequest
            _logger.info("Endpoint /handle_staging_data dipanggil")

            if not data or not data.get('type_trans') or not data.get('session'):
                raise ValueError("type_trans and session are required")

            SwaApiReceivedData = request.env['swa.api.received.data']
            records = SwaApiReceivedData.sudo().search([
                ('is_executed', '=', 'No'),
                ('type_trans', '=', data.get('type_trans'))
            ])

            if not records:
                return request.make_json_response({
                    'success': '1',
                    'error': '0',
                    'message': 'Tidak ada data yang perlu diproses'
                })

            processed = 0
            for record in records:
                json_data = record.data_trans
                try:
                    json_data = json.loads(json_data) if isinstance(json_data, str) else json_data
                except Exception:
                    _logger.error(f"Error parsing JSON for record ID {record.id}")
                    continue

                if not isinstance(json_data, list):
                    json_data = [json_data]

                handler = self._get_handler(record.type_trans)
                if handler:
                    for item in json_data:
                        handler(item)

                record.sudo().write({'is_executed': 'Yes'})
                processed += 1

            return request.make_json_response({
                'success': '1',
                'error': '0',
                'message': f'{processed} record(s) processed successfully'
            })

        except Exception as e:
            _logger.error(f"Error pada /handle_staging_data: {str(e)}")
            return request.make_json_response({
                'success': '0',
                'error': str(e),
                'message': 'Terjadi kesalahan saat memproses data'
            }, status=500)

    def _get_handler(self, type_trans):
        handlers = {
            'Item': self._process_item,
            'InventTable': self._process_item,
            'CustVend': self._process_cust_vend,
            'InventTrans': self._process_invent_trans,
            'ALL': self._process_invent_trans,
            'CustInvoiceJour': self._process_cust_invoice_jour,
            'CustInvoiceTrans': self._process_cust_invoice_trans,
            'SalesTable': self._process_sales_table,
            'SalesLine': self._process_sales_line,
            'VendInvoiceJour': self._process_vend_invoice_jour,
            'VendInvoiceTrans': self._process_vend_invoice_trans,
            'PurchTable': self._process_purch_table,
            'PurchLine': self._process_purch_line,
            'ProdTable': self._process_prod_table,
            'ProdJournalProd': self._process_prod_journal_prod,
            'ProdJournalPROD': self._process_prod_journal_prod,
            'ProdJournalBom': self._process_prod_journal_bom,
            'ProdJournalBOM': self._process_prod_journal_bom,
        }
        return handlers.get(type_trans)

    def _to_snake_case(self, key):
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', key)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def _filter_vals(self, model_name, vals):
        valid_fields = set(request.env[model_name].sudo()._fields.keys())
        return {k: v for k, v in vals.items() if k in valid_fields}

    def _parse_date(self, value):
        if isinstance(value, str) and '/' in value:
            parts = value.split('/')
            if len(parts) == 3:
                return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
        return value

    def _process_item(self, data):
        vals = self._filter_vals('swa.item.staging', {self._to_snake_case(k): v for k, v in data.items()})
        existing = request.env['swa.item.staging'].sudo().search_count([
            ('item_id', '=', data.get('ItemId'))
        ])
        if existing == 0:
            request.env['swa.item.staging'].sudo().create(vals)

    def _process_cust_vend(self, data):
        vals = self._filter_vals('swa.cust.vend.staging', {self._to_snake_case(k): v for k, v in data.items()})
        existing = request.env['swa.cust.vend.staging'].sudo().search_count([
            ('cust_vend_id', '=', data.get('CustVendId'))
        ])
        if existing == 0:
            request.env['swa.cust.vend.staging'].sudo().create(vals)

    def _process_invent_trans(self, data):
        vals = self._filter_vals('swa.invent.trans.staging', {self._to_snake_case(k): v for k, v in data.items()})
        if 'trans_date' in vals:
            vals['trans_date'] = self._parse_date(vals['trans_date'])
        existing = request.env['swa.invent.trans.staging'].sudo().search_count([
            ('orig_rec_id', '=', data.get('OrigRecId'))
        ])
        if existing == 0:
            request.env['swa.invent.trans.staging'].sudo().create(vals)

    def _process_cust_invoice_jour(self, data):
        vals = self._filter_vals('swa.cust.invoice.jour.staging', {self._to_snake_case(k): v for k, v in data.items()})
        if 'invoice_date' in vals:
            vals['invoice_date'] = self._parse_date(vals['invoice_date'])
        existing = request.env['swa.cust.invoice.jour.staging'].sudo().search_count([
            ('invoice_id', '=', data.get('InvoiceId')),
            ('invoice_date', '=', self._parse_date(data.get('InvoiceDate')))
        ])
        if existing == 0:
            request.env['swa.cust.invoice.jour.staging'].sudo().create(vals)

    def _process_cust_invoice_trans(self, data):
        vals = {self._to_snake_case(k): v for k, v in data.items()}
        if 'invoice_date' in vals:
            vals['invoice_date'] = self._parse_date(vals['invoice_date'])
        # Link to existing journal header
        jour = request.env['swa.cust.invoice.jour.staging'].sudo().search([
            ('invoice_id', '=', data.get('InvoiceId')),
            ('invoice_date', '=', self._parse_date(data.get('InvoiceDate')))
        ], limit=1)
        if jour:
            vals['jour_id'] = jour.id
        vals = self._filter_vals('swa.cust.invoice.trans.staging', vals)
        existing = request.env['swa.cust.invoice.trans.staging'].sudo().search_count([
            ('invoice_id', '=', data.get('InvoiceId')),
            ('invoice_date', '=', self._parse_date(data.get('InvoiceDate'))),
            ('purch_price', '=', data.get('PurchPrice')),
            ('line_amount', '=', data.get('LineAmount')),
        ])
        if existing == 0:
            request.env['swa.cust.invoice.trans.staging'].sudo().create(vals)

    def _process_sales_table(self, data):
        vals = self._filter_vals('swa.sales.table.staging', {self._to_snake_case(k): v for k, v in data.items()})
        existing = request.env['swa.sales.table.staging'].sudo().search_count([
            ('sales_id', '=', data.get('SalesId'))
        ])
        if existing == 0:
            request.env['swa.sales.table.staging'].sudo().create(vals)

    def _process_sales_line(self, data):
        vals = {self._to_snake_case(k): v for k, v in data.items()}
        table = request.env['swa.sales.table.staging'].sudo().search([
            ('sales_id', '=', data.get('SalesId'))
        ], limit=1)
        if table:
            vals['table_id'] = table.id
        vals = self._filter_vals('swa.sales.line.staging', vals)
        existing = request.env['swa.sales.line.staging'].sudo().search_count([
            ('sales_id', '=', data.get('SalesId')),
            ('line_num', '=', data.get('LineNum')),
        ])
        if existing == 0:
            request.env['swa.sales.line.staging'].sudo().create(vals)

    def _process_vend_invoice_jour(self, data):
        vals = self._filter_vals('swa.vend.invoice.jour.staging', {self._to_snake_case(k): v for k, v in data.items()})
        existing = request.env['swa.vend.invoice.jour.staging'].sudo().search_count([
            ('invoice_id', '=', data.get('InvoiceId')),
            ('invoice_date', '=', data.get('InvoiceDate'))
        ])
        if existing == 0:
            request.env['swa.vend.invoice.jour.staging'].sudo().create(vals)

    def _process_vend_invoice_trans(self, data):
        vals = {self._to_snake_case(k): v for k, v in data.items()}
        jour = request.env['swa.vend.invoice.jour.staging'].sudo().search([
            ('invoice_id', '=', data.get('InvoiceId')),
            ('invoice_date', '=', data.get('InvoiceDate'))
        ], limit=1)
        if jour:
            vals['jour_id'] = jour.id
        vals = self._filter_vals('swa.vend.invoice.trans.staging', vals)
        existing = request.env['swa.vend.invoice.trans.staging'].sudo().search_count([
            ('invoice_id', '=', data.get('InvoiceId')),
            ('invoice_date', '=', data.get('InvoiceDate')),
            ('line_amount', '=', data.get('LineAmount')),
        ])
        if existing == 0:
            request.env['swa.vend.invoice.trans.staging'].sudo().create(vals)

    def _process_purch_table(self, data):
        vals = self._filter_vals('swa.purch.table.staging', {self._to_snake_case(k): v for k, v in data.items()})
        existing = request.env['swa.purch.table.staging'].sudo().search_count([
            ('purch_id', '=', data.get('PurchId'))
        ])
        if existing == 0:
            request.env['swa.purch.table.staging'].sudo().create(vals)

    def _process_purch_line(self, data):
        vals = {self._to_snake_case(k): v for k, v in data.items()}
        table = request.env['swa.purch.table.staging'].sudo().search([
            ('purch_id', '=', data.get('PurchId'))
        ], limit=1)
        if table:
            vals['table_id'] = table.id
        vals = self._filter_vals('swa.purch.line.staging', vals)
        existing = request.env['swa.purch.line.staging'].sudo().search_count([
            ('purch_id', '=', data.get('PurchId')),
            ('item_id', '=', data.get('ItemId')),
        ])
        if existing == 0:
            request.env['swa.purch.line.staging'].sudo().create(vals)

    def _process_prod_table(self, data):
        vals = self._filter_vals('swa.prod.table.staging', {self._to_snake_case(k): v for k, v in data.items()})
        existing = request.env['swa.prod.table.staging'].sudo().search_count([
            ('prod_id', '=', data.get('ProdId'))
        ])
        if existing == 0:
            request.env['swa.prod.table.staging'].sudo().create(vals)

    def _process_prod_journal_prod(self, data):
        vals = {self._to_snake_case(k): v for k, v in data.items()}
        table = request.env['swa.prod.table.staging'].sudo().search([
            ('prod_id', '=', data.get('ProdId'))
        ], limit=1)
        if table:
            vals['table_id'] = table.id
        vals = self._filter_vals('swa.prod.journal.prod.staging', vals)
        existing = request.env['swa.prod.journal.prod.staging'].sudo().search_count([
            ('prod_id', '=', data.get('ProdId')),
            ('item_id', '=', data.get('ItemId')),
        ])
        if existing == 0:
            request.env['swa.prod.journal.prod.staging'].sudo().create(vals)

    def _process_prod_journal_bom(self, data):
        vals = {self._to_snake_case(k): v for k, v in data.items()}
        table = request.env['swa.prod.table.staging'].sudo().search([
            ('prod_id', '=', data.get('ProdId'))
        ], limit=1)
        if table:
            vals['table_id'] = table.id
        vals = self._filter_vals('swa.prod.journal.bom.staging', vals)
        existing = request.env['swa.prod.journal.bom.staging'].sudo().search_count([
            ('prod_id', '=', data.get('ProdId')),
            ('item_id', '=', data.get('ItemId')),
        ])
        if existing == 0:
            request.env['swa.prod.journal.bom.staging'].sudo().create(vals)
