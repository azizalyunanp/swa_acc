from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class SwaPurchTableStaging(models.Model):
    _name = 'swa.purch.table.staging'
    _description = 'Purchase Table Staging (AX 2012)'

    purch_id = fields.Char(string='Purchase ID')
    order_account = fields.Char(string='Order Account')
    purchase_type = fields.Char(string='Purchase Type')
    tax_group = fields.Char(string='Tax Group')
    document_status = fields.Char(string='Document Status')
    accounting_date = fields.Char(string='Accounting Date')
    created_date = fields.Char(string='Created Date')
    purch_status = fields.Char(string='Purch Status')
    default_dimension = fields.Char(string='Default Dimension')
    dlv_mode = fields.Char(string='Dlv Mode')
    dlv_term = fields.Char(string='Dlv Term')
    payment = fields.Char(string='Payment')
    purch_pool_id = fields.Char(string='Purch Pool ID')
    posting_profile = fields.Char(string='Posting Profile')
    currency_code = fields.Char(string='Currency Code')
    purch_name = fields.Char(string='Purch Name')
    invent_site_id = fields.Char(string='Invent Site ID')
    invent_location_id = fields.Char(string='Invent Location ID')
    delivery_date = fields.Char(string='Delivery Date')
    department = fields.Char(string='Department')
    disc_percent = fields.Float(string='Disc Percent')
    is_executed = fields.Selection([
        ('No', 'No'),
        ('Yes', 'Yes')
    ], string='Is Executed', default='No')
    log = fields.Text(string='Log')
    line_ids = fields.One2many(
        'swa.purch.line.staging', 'table_id',
        string='Purchase Lines')

    def action_create_purchase_order(self):
        for rec in self:
            try:
                # Duplicate check
                existing_po = self.env['purchase.order'].sudo().search([
                    ('name', '=', rec.purch_id)
                ], limit=1)
                if existing_po:
                    rec.write({
                        'is_executed': 'Yes',
                        'log': f"Skipped: Purchase Order '{rec.purch_id}' already exists (ID: {existing_po.id})"
                    })
                    continue

                partner = self.env['res.partner'].sudo().search([
                    ('ref', '=', rec.order_account)
                ], limit=1)
                if not partner:
                    rec.write({'log': f"Error: Partner with ref '{rec.order_account}' not found. Purchase Order not created."})
                    continue

                currency = self.env['res.currency'].sudo().search([
                    ('name', '=', rec.currency_code)
                ], limit=1) if rec.currency_code else False

                # Resolve company from staging setup
                setup = self.env['swa.staging.setup'].sudo().search([
                    ('invent_site_id', '=', rec.invent_site_id),
                    ('active', '=', True),
                ], limit=1)

                # Link any unlinked PurchLine records with matching purch_id
                unlinked = self.env['swa.purch.line.staging'].sudo().search([
                    ('purch_id', '=', rec.purch_id),
                    ('table_id', '=', False),
                ])
                if unlinked:
                    unlinked.write({'table_id': rec.id})

                # Validate all lines have valid products first
                all_lines_valid = True
                line_products = []
                for line in rec.line_ids:
                    product = self.env['product.product'].sudo().search([
                        ('default_code', '=', line.item_id)
                    ], limit=1) if line.item_id else False
                    if not product:
                        msg = f"Error: Item ID '{line.item_id}' not found. Purchase Order not created." if line.item_id else "Error: Item ID is empty. Purchase Order not created."
                        line.write({'log': msg})
                        all_lines_valid = False
                        continue
                    line_products.append((line, product))

                if not all_lines_valid:
                    rec.write({'log': f"Error: One or more products not found for Purchase ID '{rec.purch_id}'. Purchase Order not created."})
                    continue

                # Auto-create warehouse if invent_location_id not found
                wh = False
                if rec.invent_location_id:
                    wh = self.env['stock.warehouse'].sudo().search([
                        ('code', '=ilike', rec.invent_location_id.strip())
                    ], limit=1)
                    if not wh:
                        wh_company = setup.company_id if setup else self.env.company
                        wh = self.env['stock.warehouse'].sudo().create({
                            'name': rec.invent_location_id,
                            'code': rec.invent_location_id,
                            'company_id': wh_company.id,
                        })
                        _logger.info(f"Created warehouse: {rec.invent_location_id} (ID: {wh.id})")

                # All validation passed: create order
                order = self.env['purchase.order'].sudo().create({
                    'name': rec.purch_id,
                    'partner_id': partner.id,
                    'currency_id': currency.id if currency else False,
                    'company_id': setup.company_id.id if setup else False,
                    'partner_ref': rec.purch_id,
                })
                lines_created = 0

                for line, product in line_products:
                    uom = self.env['uom.uom'].sudo().search([
                        ('name', '=ilike', (line.purch_unit or '').strip())
                    ], limit=1) if line.purch_unit else False

                    tax = False
                    if line.tax_group:
                        tax = self.env['account.tax'].sudo().search([
                            ('name', '=', line.tax_group),
                            ('type_tax_use', '=', 'purchase'),
                            ('company_id', '=', setup.company_id.id if setup else False),
                        ], limit=1)

                    self.env['purchase.order.line'].sudo().create({
                        'order_id': order.id,
                        'product_id': product.id,
                        'product_qty': line.purch_qty or 0,
                        'price_unit': line.purch_price or 0,
                        'product_uom': uom.id if uom else product.uom_id.id,
                        'taxes_id': [(6, 0, [tax.id])] if tax else False,
                        'name': product.name,
                    })
                    line.write({
                        'is_executed': 'Yes',
                        'log': f"Success: Purchase Order Line created (Order: {order.name})"
                    })
                    lines_created += 1

                order.button_confirm()
                rec.write({
                    'is_executed': 'Yes',
                    'log': f"Success: Purchase Order created (ID: {order.id}, Name: {order.name}, State: purchase) with {lines_created} line(s)"
                })

            except Exception as e:
                rec.write({'log': f"Error: {str(e)}"})
                _logger.error(f"PurchTableStaging {rec.id} action_create_purchase_order error: {str(e)}")
