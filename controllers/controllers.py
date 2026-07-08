# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
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

            SwaApiReceivedData = request.env['swa.api.received.data']
            new_data = SwaApiReceivedData.sudo().create({
                'type_trans': data.get('type_trans'),
                'session': data.get('session'),
                'data_trans': json.dumps(data.get('data_trans')),
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

        return request.make_json_response(response)

    @http.route('/synchronize_data/test', type='http', auth="public", methods=['GET'])
    def test_endpoint(self, **kwargs):
        return "Endpoint synchronize_data berfungsi dengan baik!"
