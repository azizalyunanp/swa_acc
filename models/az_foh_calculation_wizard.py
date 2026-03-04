# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from collections import defaultdict


FOH_TYPES = [
    'electricity',
    'wage',
    'overtime',
    'others',
    'sparepart',
    'fuel',
    'depreciation',
    'work_order',
    'packing',
]

# Map FOH type → field suffix on az.foh.calculation
FOH_FIELD_MAP = {
    'electricity': 'electricity',
    'wage': 'wage',
    'overtime': 'overtime',
    'others': 'others',
    'sparepart': 'sparepart',
    'fuel': 'fuel',
    'depreciation': 'depreciation',
    'work_order': 'workorder',
    'packing': 'packing',
}


class AzFohCalculationWizard(models.TransientModel):
    _name = 'az.foh.calculation.wizard'
    _description = 'FOH Calculation Wizard'

    from_date = fields.Date(
        string='From Date',
        required=True,
    )
    to_date = fields.Date(
        string='To Date',
        required=True,
    )
    location_id = fields.Many2one(
        comodel_name='stock.location',
        string='Location',
        required=True,
        domain=[('usage', '=', 'internal')],
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    def calc_foh(self):
        self.ensure_one()

        if self.from_date > self.to_date:
            raise UserError(_("From Date cannot be greater than To Date."))

        # ─────────────────────────────────────────────────────────────
        # STEP 1: Query mrp.production (state=done, date & location)
        # ─────────────────────────────────────────────────────────────
        productions = self.env['mrp.production'].search([
            ('state', '=', 'done'),
            ('date_start', '>=', self.from_date),
            ('date_start', '<=', self.to_date),
            ('location_dest_id', '=', self.location_id.id),
        ])

        if not productions:
            raise UserError(_("No finished production orders found for the given parameters."))

        # ─────────────────────────────────────────────────────────────
        # STEP 2: Aggregate qty_producing per product
        # ─────────────────────────────────────────────────────────────
        product_data = defaultdict(lambda: {
            'qty_raf': 0.0,
            'uom_id': False,
        })

        for prod in productions:
            pid = prod.product_id.id
            product_data[pid]['qty_raf'] += prod.qty_producing
            if not product_data[pid]['uom_id']:
                product_data[pid]['uom_id'] = prod.product_id.uom_id.id

        # ─────────────────────────────────────────────────────────────
        # STEP 3: Fetch ratios from az.item.foh.ratio per product
        # ─────────────────────────────────────────────────────────────
        ratio_records = self.env['az.item.foh.ratio'].search([
            ('product_id', 'in', list(product_data.keys())),
        ])
        ratio_map = {r.product_id.id: r.ratio for r in ratio_records}

        # Compute prod_equ per product
        for pid, data in product_data.items():
            ratio = ratio_map.get(pid, 0.0)
            data['ratio'] = ratio
            data['prod_equ'] = data['qty_raf'] * ratio

        # ─────────────────────────────────────────────────────────────
        # STEP 4: Compute total prod_equ → prod_equ_weight per product
        # ─────────────────────────────────────────────────────────────
        total_prod_equ = sum(d['prod_equ'] for d in product_data.values())

        for pid, data in product_data.items():
            if total_prod_equ:
                data['prod_equ_weight'] = data['prod_equ'] / total_prod_equ
            else:
                data['prod_equ_weight'] = 0.0

        # ─────────────────────────────────────────────────────────────
        # STEP 5: Fetch COA amounts per FOH type from account.move.line
        # ─────────────────────────────────────────────────────────────
        mapping_records = self.env['az.mapping.account.foh'].search([
            ('type', '!=', 'none'),
        ])

        # Build: {foh_type: [account_id, ...]}
        type_account_map = defaultdict(list)
        for m in mapping_records:
            type_account_map[m.type].append(m.account_id.id)

        # Fetch account.move.line amounts per type
        coa_amounts = {}
        for foh_type, account_ids in type_account_map.items():
            if not account_ids:
                coa_amounts[foh_type] = 0.0
                continue
            move_lines = self.env['account.move.line'].search([
                ('account_id', 'in', account_ids),
                ('date', '>=', self.from_date),
                ('date', '<=', self.to_date),
                ('company_id', '=', self.company_id.id),
                ('parent_state', '=', 'posted'),
            ])
            coa_amounts[foh_type] = sum(
                line.debit - line.credit for line in move_lines
            )

        # ─────────────────────────────────────────────────────────────
        # STEP 6: Delete existing records for this period then recreate
        # ─────────────────────────────────────────────────────────────
        self.env['az.foh.calculation'].search([
            ('trans_date', '>=', self.from_date),
            ('trans_date', '<=', self.to_date),
        ]).unlink()

        # ─────────────────────────────────────────────────────────────
        # STEP 7: Build and create new az.foh.calculation records
        # ─────────────────────────────────────────────────────────────
        vals_list = []
        for pid, data in product_data.items():
            prod_equ_weight = data['prod_equ_weight']
            vals = {
                'trans_date': self.from_date,
                'location_id': self.location_id.id,
                'product_id': pid,
                'qty_raf': data['qty_raf'],
                'uom': data['uom_id'],
                'qty_raf_convert': data['qty_raf'],
                'uom_convert': data['uom_id'],
                'ratio': data['ratio'],
                'prod_equ': data['prod_equ'],
                'prod_equ_weight': prod_equ_weight,
            }

            for foh_type in FOH_TYPES:
                field_suffix = FOH_FIELD_MAP[foh_type]
                coa_amount = coa_amounts.get(foh_type, 0.0)
                percent = prod_equ_weight * 100
                amount = (percent / 100.0) * coa_amount

                vals[f'percent_{field_suffix}'] = percent
                vals[f'amount_{field_suffix}'] = amount

            vals_list.append(vals)

        self.env['az.foh.calculation'].create(vals_list)

        # Return action to refresh the FOH Calculation list view
        return {
            'type': 'ir.actions.act_window',
            'name': _('FOH Calculation'),
            'res_model': 'az.foh.calculation',
            'view_mode': 'list,form',
            'target': 'current',
        }
