from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


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

    def action_create_mo(self):
        for rec in self:
            try:
                existing = self.env['mrp.production'].sudo().search([
                    ('name', '=', rec.prod_id)
                ], limit=1)
                if existing:
                    rec.write({
                        'is_executed': 'Yes',
                        'log': f"Skipped: MO '{rec.prod_id}' already exists (ID: {existing.id})"
                    })
                    continue

                product = self.env['product.product'].sudo().search([
                    ('default_code', '=', rec.item_id)
                ], limit=1) if rec.item_id else False
                if not product:
                    rec.write({'log': f"Error: Product '{rec.item_id}' not found."})
                    continue

                # Resolve company from staging setup
                company = False
                if rec.site:
                    setup = self.env['swa.staging.setup'].sudo().search([
                        ('invent_site_id', '=', rec.site),
                        ('active', '=', True),
                    ], limit=1)
                    if setup:
                        company = setup.company_id

                company_ids = [company.id] if company else self.env.company.ids
                ctx = {'allowed_company_ids': company_ids}

                # Auto-create warehouse
                wh = False
                if rec.warehouse:
                    wh = self.env['stock.warehouse'].sudo().search([
                        ('code', '=ilike', rec.warehouse.strip())
                    ], limit=1)
                    if not wh:
                        wh = self.env['stock.warehouse'].sudo().create({
                            'name': rec.warehouse,
                            'code': rec.warehouse,
                            'company_id': company.id if company else self.env.company.id,
                        })

                # Calculate total FG qty from ProdJournalProd (only matching item_id)
                total_qty = sum(line.qty or 0 for line in rec.line_ids_prod if line.item_id == rec.item_id)

                # Create MO
                mo_vals = {
                    'name': rec.prod_id,
                    'product_id': product.id,
                    'product_qty': total_qty,
                    'qty_producing':total_qty,
                    'product_qty':total_qty,
                    'product_uom_id': product.uom_id.id,
                    'bom_id': False,
                    'company_id': company.id if company else False,
                }
                if wh:
                    picking_type = self.env['stock.picking.type'].sudo().search([
                        ('code', '=', 'mrp_manufacturing'),
                        ('warehouse_id', '=', wh.id),
                    ], limit=1)
                    if picking_type:
                        mo_vals['picking_type_id'] = picking_type.id

                mo = self.env['mrp.production'].sudo().with_context(**ctx).create(mo_vals)

                # # Confirm first (creates FG move + sets locations)
                mo.sudo().with_context(**ctx).action_confirm()

                # Add raw materials from ProdJournalBom (group by item_id + lot, sum qty)
                bom_grouped = {}
                for bom_line in rec.line_ids_bom:
                    if bom_line.item_id:
                        key = (bom_line.item_id, bom_line.lot or '')
                        if key not in bom_grouped:
                            bom_grouped[key] = 0
                        bom_grouped[key] += (bom_line.qty or 0)
                    bom_line.write({
                        'is_executed': 'Yes',
                        'log': f"Success: MO component (MO: {mo.name})"
                    })

                # Compute price_unit per (item_id, lot_name) once
                price_map = {}
                mo_date = mo.date_start or fields.Datetime.now()
                for (item_id, lot_name), total_qty in bom_grouped.items():
                    bom_product = self.env['product.product'].sudo().search([
                        ('default_code', '=', item_id)
                    ], limit=1) if item_id else False
                    if not bom_product:
                        continue
                    # Base price from product/lot standard_price
                    price = bom_product.standard_price or 0.0
                    if bom_product.tracking in ('lot', 'serial') and lot_name:
                        lot = self.env['stock.lot'].sudo().search([
                            ('product_id', '=', bom_product.id),
                            ('name', '=', lot_name),
                            ('company_id', '=', company.id if company else False),
                        ], limit=1)
                        if lot and lot.standard_price:
                            price = lot.standard_price
                        elif bom_product.lot_valuated and lot and price:
                            lot.sudo().write({'standard_price': price})
                    # SVL lookup by date ONLY if price is still 0
                    if not price:
                        svl = self.env['stock.valuation.layer'].sudo().search([
                            ('product_id', '=', bom_product.id),
                            ('create_date', '<=', mo_date),
                            ('quantity', '>', 0),
                        ], limit=1, order='create_date desc, id desc')
                        if svl and svl.unit_cost:
                            price = svl.unit_cost
                    price_map[(item_id, lot_name)] = price

                # Create raw material stock.moves
                for (item_id, lot_name), total_qty in bom_grouped.items():
                    bom_product = self.env['product.product'].sudo().search([
                        ('default_code', '=', item_id)
                    ], limit=1) if item_id else False
                    if not bom_product:
                        continue
                    price_unit = price_map.get((item_id, lot_name), bom_product.standard_price or 0.0)
                    try:
                        move = self.env['stock.move'].sudo().with_context(**ctx).create({
                            'name': bom_product.name,
                            'product_id': bom_product.id,
                            'product_uom_qty': total_qty,
                            'quantity': total_qty,
                            'picked': True,
                            'price_unit': price_unit,
                            'product_uom': bom_product.uom_id.id,
                            'raw_material_production_id': mo.id,
                            'location_id': mo.location_src_id.id,
                            'location_dest_id': mo.location_dest_id.id,
                            'picking_type_id': mo.picking_type_id.id,
                            'company_id': company.id if company else False,
                            'bom_line_id': False,
                        })
                        move.sudo()._action_confirm()
                    except Exception as move_err:
                        _logger.error(f"ProdTableStaging {rec.id}: Failed to create stock.move for {item_id}: {move_err}")

                # Build lot map from grouped data (item_id, lot_name) -> lot object
                for (item_id, lot_name), total_qty in bom_grouped.items():
                    if not lot_name:
                        continue
                    bom_product = self.env['product.product'].sudo().search([
                        ('default_code', '=', item_id)
                    ], limit=1) if item_id else False
                    if not bom_product or bom_product.tracking == 'none':
                        continue
                    lot = self.env['stock.lot'].sudo().search([
                        ('product_id', '=', bom_product.id),
                        ('name', '=', lot_name),
                    ], limit=1)
                    if lot:
                        # Reuse existing lot, set company from staging setup
                        lot.sudo().write({'company_id': company.id if company else lot.company_id.id})
                    else:
                        lot = self.env['stock.lot'].sudo().create({
                            'product_id': bom_product.id,
                            'name': lot_name,
                            'company_id': company.id if company else self.env.company.id,
                            'standard_price': price_map.get((item_id, lot_name), bom_product.standard_price or 0.0),
                        })
                    # Set lot on the matching stock.move.line
                    for move in mo.move_raw_ids:
                        if move.product_id.id != bom_product.id:
                            continue
                        for move_line in move.move_line_ids:
                            if not move_line.lot_id:
                                move_line.sudo().write({'lot_id': lot.id})
                                break

                # Set lot_producing_id from ProdJournalProd (first matching item_id lot)
                prod_lot = False
                for prod_line in rec.line_ids_prod:
                    if prod_line.item_id == rec.item_id and prod_line.lot:
                        prod_lot = self.env['stock.lot'].sudo().search([
                            ('product_id', '=', product.id),
                            ('name', '=', prod_line.lot),
                        ], limit=1)
                        if prod_lot:
                            prod_lot.sudo().write({'company_id': company.id if company else prod_lot.company_id.id})
                        else:
                            prod_lot = self.env['stock.lot'].sudo().create({
                                'product_id': product.id,
                                'name': prod_line.lot,
                                'company_id': company.id if company else self.env.company.id,
                                'standard_price': product.standard_price or 0.0,
                            })
                        mo.sudo().write({'lot_producing_id': prod_lot.id})
                        break
                mo.sudo().with_context(**ctx).button_mark_done()

                # Mark ProdJournalProd records as done
                for prod_line in rec.line_ids_prod:
                    if prod_line.item_id == rec.item_id:
                        prod_line.write({
                            'is_executed': 'Yes',
                            'log': f"Success: MO FG produced (MO: {mo.name})"
                        })

                rec.write({
                    'is_executed': 'Yes',
                    'log': f"Success: MO created & done (ID: {mo.id}, Name: {mo.name}, Qty: {total_qty})"
                })

            except Exception as e:
                rec.write({'log': f"Error: {str(e)}"})
                _logger.error(f"ProdTableStaging {rec.id} action_create_mo error: {str(e)}")