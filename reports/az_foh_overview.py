# -*- coding: utf-8 -*-

from odoo import api, models


class AzReportFohOverview(models.AbstractModel):
    _name = 'report.swa_acc.az_foh_overview_report'
    _description = 'FOH Production Cost Overview Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """PDF endpoint — one doc per mrp.production."""
        docs = []
        for prod_id in docids:
            doc = self._get_foh_report_data(prod_id)
            docs.append(doc)
        return {
            'doc_ids':   docids,
            'doc_model': 'mrp.production',
            'docs':      docs,
        }

    @api.model
    def _get_foh_report_data(self, production_id):
        mrp = self.env['mrp.production'].browse(production_id)
        currency = mrp.company_id.currency_id or self.env.company.currency_id

        # ── Raw materials ─────────────────────────────────────────────
        raw_lines = []
        total_raw_cost = 0.0

        for move in mrp.move_raw_ids.filtered(lambda m: m.state == 'done'):
            for ml in move.move_line_ids:
                qty = ml.quantity
                if qty <= 0:
                    continue
                product = ml.product_id
                if product.tracking == 'lot' and ml.lot_id:
                    price = (
                        ml.lot_id.standard_price
                        if hasattr(ml.lot_id, 'standard_price') and ml.lot_id.standard_price
                        else product.standard_price
                    )
                    lot_name = ml.lot_id.name
                else:
                    price = product.standard_price
                    lot_name = ''

                line_total = qty * price
                total_raw_cost += line_total

                raw_lines.append({
                    'product_code': product.default_code or '',
                    'product_name': product.name,
                    'lot_name':     lot_name,
                    'qty':          qty,
                    'uom_name':     ml.product_uom_id.name if ml.product_uom_id else '',
                    'unit_price':   currency.round(price),
                    'total_price':  currency.round(line_total),
                })

        # ── FOH Production Cost records ───────────────────────────────
        foh_records = self.env['az.foh.production.cost'].search([
            ('mrp_production_id', '=', mrp.id),
        ])

        foh_lines = []
        total_foh_cost = 0.0

        for rec in foh_records:
            total_foh_cost += rec.cost_price_foh
            foh_lines.append({
                'product_code': rec.product_id_foh.default_code or '',
                'product_name': rec.product_name_foh or rec.product_id_foh.name,
                'qty':          rec.product_foh_qty,
                'cost_price':   currency.round(rec.cost_price_foh),
            })

        # ── Summary ───────────────────────────────────────────────────
        qty_producing  = mrp.qty_producing or 0.0
        total_cost     = total_raw_cost + total_foh_cost
        cost_per_unit  = (total_cost / qty_producing) if qty_producing > 0 else 0.0

        # FG price after recalculation
        fg_product    = mrp.product_id
        current_price = 0.0
        if fg_product.tracking == 'lot' and mrp.lot_producing_id:
            lot = mrp.lot_producing_id
            current_price = (
                lot.standard_price
                if hasattr(lot, 'standard_price')
                else fg_product.standard_price
            )
        else:
            current_price = fg_product.standard_price

        return {
            'name':            mrp.name,
            'product_code':    fg_product.default_code or '',
            'product_name':    fg_product.name,
            'lot_producing':   mrp.lot_producing_id.name if mrp.lot_producing_id else '',
            'qty_producing':   qty_producing,
            'uom_name':        mrp.product_uom_id.name if mrp.product_uom_id else '',
            'location':        mrp.location_dest_id.display_name if mrp.location_dest_id else '',
            'date_start':      mrp.date_start,
            'currency':        currency,
            'raw_lines':       raw_lines,
            'foh_lines':       foh_lines,
            'total_raw_cost':  currency.round(total_raw_cost),
            'total_foh_cost':  currency.round(total_foh_cost),
            'total_cost':      currency.round(total_cost),
            'cost_per_unit':   currency.round(cost_per_unit),
            'current_price':   currency.round(current_price),
        }
