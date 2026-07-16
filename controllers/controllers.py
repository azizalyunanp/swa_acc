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
            'CustVend': self._process_cust_vend,
            'InventTrans': self._process_invent_trans,
            'CustInvoiceJour': self._process_cust_invoice_jour,
            'CustInvoiceTrans': self._process_cust_invoice_trans,
        }
        return handlers.get(type_trans)

    def _to_snake_case(self, key):
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', key)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def _process_item(self, data):
        vals = {self._to_snake_case(k): v for k, v in data.items()}
        existing = request.env['swa.item.staging'].sudo().search_count([
            ('item_id', '=', data.get('ItemId'))
        ])
        if existing == 0:
            request.env['swa.item.staging'].sudo().create(vals)

    def _process_cust_vend(self, data):
        vals = {self._to_snake_case(k): v for k, v in data.items()}
        existing = request.env['swa.cust.vend.staging'].sudo().search_count([
            ('cust_vend_id', '=', data.get('CustVendId'))
        ])
        if existing == 0:
            request.env['swa.cust.vend.staging'].sudo().create(vals)

    def _process_invent_trans(self, data):
        vals = {self._to_snake_case(k): v for k, v in data.items()}
        existing = request.env['swa.invent.trans.staging'].sudo().search_count([
            ('orig_rec_id', '=', data.get('OrigRecId'))
        ])
        if existing == 0:
            request.env['swa.invent.trans.staging'].sudo().create(vals)

    def _process_cust_invoice_jour(self, data):
        vals = {self._to_snake_case(k): v for k, v in data.items()}
        existing = request.env['swa.cust.invoice.jour.staging'].sudo().search_count([
            ('invoice_id', '=', data.get('InvoiceId')),
            ('invoice_date', '=', data.get('InvoiceDate'))
        ])
        if existing == 0:
            request.env['swa.cust.invoice.jour.staging'].sudo().create(vals)

    def _process_cust_invoice_trans(self, data):
        vals = {self._to_snake_case(k): v for k, v in data.items()}
        # Link to existing journal header
        jour = request.env['swa.cust.invoice.jour.staging'].sudo().search([
            ('invoice_id', '=', data.get('InvoiceId')),
            ('invoice_date', '=', data.get('InvoiceDate'))
        ], limit=1)
        if jour:
            vals['jour_id'] = jour.id
        existing = request.env['swa.cust.invoice.trans.staging'].sudo().search_count([
            ('invoice_id', '=', data.get('InvoiceId')),
            ('invoice_date', '=', data.get('InvoiceDate')),
            ('purch_price', '=', data.get('PurchPrice')),
            ('line_amount', '=', data.get('LineAmount')),
        ])
        if existing == 0:
            request.env['swa.cust.invoice.trans.staging'].sudo().create(vals)
