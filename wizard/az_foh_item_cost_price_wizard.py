# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import calendar


# Map az.mapping.item.foh.type → field on az.foh.calculation
FOH_TYPE_AMOUNT_MAP = {
    'electricity': 'amount_electricity',
    'wage':        'amount_wage',
    'overtime':    'amount_overtime',
    'others':      'amount_others',
    'sparepart':   'amount_sparepart',
    'fuel':        'amount_fuel',
    'depreciation':'amount_depreciation',
    'work_order':  'amount_workorder',
    'packing':     'amount_packing',
}


class AzFohItemCostPriceWizard(models.TransientModel):
    _name = 'az.foh.item.cost.price.wizard'
    _description = 'FOH Item Cost Price Wizard'

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

    def calc_foh_item_cost_price(self):
        self.ensure_one()

        # ─────────────────────────────────────────────────────────────
        # STEP 1: Get az.foh.calculation where trans_date & location_id
        #         and qty_raf != 0
        # ─────────────────────────────────────────────────────────────
        foh_calcs = self.env['az.foh.calculation'].search([
            ('trans_date', '>=', self.from_date),
            ('trans_date', '<=', self.to_date),
            ('location_id', '=', self.location_id.id),
            ('qty_raf', '!=', 0),
        ])

        if not foh_calcs:
            raise UserError(_(
                "No FOH Calculation data found for period %s - %s and Location: %s.\n"
                "Please run FOH Calculation first."
            ) % (self.from_date, self.to_date, self.location_id.display_name))

        # ─────────────────────────────────────────────────────────────
        # STEP 2: Get all az.mapping.item.foh (FOH Item Mapping)
        # ─────────────────────────────────────────────────────────────
        foh_item_mappings = self.env['az.mapping.item.foh'].search([
            ('type', '!=', 'none'),
        ])

        if not foh_item_mappings:
            raise UserError(_("No FOH Item Mapping found. Please configure FOH Mapping Item first."))

        # ─────────────────────────────────────────────────────────────
        # STEP 3: Fetch IDR currency
        # ─────────────────────────────────────────────────────────────
        idr_currency = self.env['res.currency'].search([('name', '=', 'IDR')], limit=1)

        # ─────────────────────────────────────────────────────────────
        # STEP 4: Delete existing records for same trans_date & location
        # ─────────────────────────────────────────────────────────────
        self.env['az.foh.item.cost.price'].search([
            ('trans_date', '>=', self.from_date),
            ('trans_date', '<=', self.to_date),
            ('location_id', '=', self.location_id.id),
        ]).unlink()

        # ─────────────────────────────────────────────────────────────
        # STEP 5: Loop az.foh.calculation × az.mapping.item.foh
        #         (analogous to nested while select in X++)
        # ─────────────────────────────────────────────────────────────
        vals_list = []
        for calc in foh_calcs:
            qty_raf = calc.qty_raf
            # trans_date = last day of calc.trans_date's month
            from datetime import date as dt_date
            last_day = calendar.monthrange(calc.trans_date.year, calc.trans_date.month)[1]
            item_trans_date = dt_date(calc.trans_date.year, calc.trans_date.month, last_day)

            for mapping in foh_item_mappings:
                # Get the correct amount field based on mapping type
                amount_field = FOH_TYPE_AMOUNT_MAP.get(mapping.type, None)
                if not amount_field:
                    continue

                raw_amount = getattr(calc, amount_field, 0.0)
                amount = raw_amount / qty_raf if qty_raf else 0.0

                # Duplicate check
                if self.env['az.foh.item.cost.price'].search([
                    ('product_id', '=', calc.product_id.id),
                    ('product_id_foh', '=', mapping.product_id.id),
                    ('trans_date', '=', item_trans_date),
                    ('location_id', '=', self.location_id.id),
                ], limit=1):
                    raise ValidationError(
                        _("FOH Item Cost Price already exists for product '%s' / FOH item '%s' on %s.\n"
                          "Please delete the existing data first.")
                        % (calc.product_id.display_name, mapping.product_id.display_name, item_trans_date)
                    )

                vals_list.append({
                    'product_id':     calc.product_id.id,
                    'trans_date':     item_trans_date,
                    'location_id':    self.location_id.id,
                    'company_id':     self.company_id.id,
                    'product_id_foh': mapping.product_id.id,
                    'uom_id':         calc.uom.id,
                    'currency_id':    idr_currency.id if idr_currency else False,
                    'amount':         amount,
                })

        if vals_list:
            self.env['az.foh.item.cost.price'].create(vals_list)

        return {
            'type': 'ir.actions.act_window',
            'name': _('FOH Item Cost Price'),
            'res_model': 'az.foh.item.cost.price',
            'view_mode': 'list,form',
            'target': 'current',
        }
