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

                # Confirm first (creates FG move + sets locations)
                mo.sudo().with_context(**ctx).action_confirm()

                # Add raw materials from ProdJournalBom (AFTER confirm)
                for bom_line in rec.line_ids_bom:
                    bom_product = self.env['product.product'].sudo().search([
                        ('default_code', '=', bom_line.item_id)
                    ], limit=1) if bom_line.item_id else False
                    if not bom_product:
                        bom_line.write({'log': f"Error: BOM product '{bom_line.item_id}' not found."})
                        continue
                    try:
                        self.env['stock.move'].sudo().with_context(**ctx).create({
                            'name': bom_product.name,
                            'product_id': bom_product.id,
                            'product_uom_qty': bom_line.qty or 0,
                            'product_uom': bom_product.uom_id.id,
                            'production_id': mo.id,
                            'raw_material_production_id': mo.id,
                            'location_id': mo.location_src_id.id,
                            'location_dest_id': mo.location_dest_id.id,
                            'company_id': company.id if company else False,
                            'bom_line_id': False,
                        })
                        bom_line.write({
                            'is_executed': 'Yes',
                            'log': f"Success: MO component created (MO: {mo.name})"
                        })
                    except Exception as move_err:
                        bom_line.write({'log': f"Error creating stock.move: {str(move_err)}"})
                        _logger.error(f"ProdTableStaging {rec.id}: Failed to create stock.move for {bom_line.item_id}: {move_err}")

                # Build lot map from staging data (item_id -> lot)
                lot_map = {}
                for bom_line in rec.line_ids_bom:
                    if bom_line.item_id and bom_line.lot:
                        lot_map[bom_line.item_id] = bom_line.lot
                for prod_line in rec.line_ids_prod:
                    if prod_line.item_id and prod_line.lot:
                        lot_map[prod_line.item_id] = prod_line.lot

                # Set lot_producing_id from ProdJournalProd (first matching item_id lot)
                prod_lot = False
                for prod_line in rec.line_ids_prod:
                    if prod_line.item_id == rec.item_id and prod_line.lot:
                        prod_lot = self.env['stock.lot'].sudo().search([
                            ('product_id', '=', product.id),
                            ('name', '=', prod_line.lot),
                            ('company_id', '=', company.id if company else False),
                        ], limit=1)
                        if not prod_lot:
                            prod_lot = self.env['stock.lot'].sudo().create({
                                'product_id': product.id,
                                'name': prod_line.lot,
                                'company_id': company.id if company else self.env.company.id,
                            })
                        mo.sudo().write({'lot_producing_id': prod_lot.id})
                        break

                # Set lots on stock.move.line
                for move in mo.move_raw_ids | mo.move_finished_ids:
                    if move.product_id.tracking in ('none', False):
                        continue
                    staging_lot = lot_map.get(move.product_id.default_code)
                    if not staging_lot:
                        continue
                    for move_line in move.move_line_ids:
                        if move_line.lot_id:
                            continue
                        lot = self.env['stock.lot'].sudo().search([
                            ('product_id', '=', move.product_id.id),
                            ('name', '=', staging_lot),
                            ('company_id', '=', company.id if company else False),
                        ], limit=1)
                        if not lot:
                            lot = self.env['stock.lot'].sudo().create({
                                'product_id': move.product_id.id,
                                'name': staging_lot,
                                'company_id': company.id if company else self.env.company.id,
                            })
                        move_line.sudo().write({'lot_id': lot.id})

                mo.qty_producing = total_qty
                # mo.sudo().with_context(**ctx).button_mark_done()

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