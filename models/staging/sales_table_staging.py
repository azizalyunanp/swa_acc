from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class SwaSalesTableStaging(models.Model):
    _name = 'swa.sales.table.staging'
    _description = 'Sales Table Staging (AX 2012)'

    sales_id = fields.Char(string='Sales ID')
    cust_account = fields.Char(string='Cust Account')
    price_group_id = fields.Char(string='Price Group ID')
    sales_pool_id = fields.Char(string='Sales Pool ID')
    invoice_account = fields.Char(string='Invoice Account')
    cust_group = fields.Char(string='Cust Group')
    incl_tax = fields.Char(string='Include Tax')
    sales_type = fields.Char(string='Sales Type')
    currency_code = fields.Char(string='Currency Code')
    cust_name = fields.Char(string='Cust Name')
    delivery_date = fields.Char(string='Delivery Date')
    delivery_name = fields.Char(string='Delivery Name')
    disc_percent = fields.Float(string='Disc Percent')
    dlv_mode = fields.Char(string='Dlv Mode')
    dlv_term = fields.Char(string='Dlv Term')
    payment = fields.Char(string='Payment')
    posting_profile = fields.Char(string='Posting Profile')
    payment_sched = fields.Char(string='Payment Sched')
    paym_mode = fields.Char(string='Paym Mode')
    sales_id_ref = fields.Char(string='Sales ID Ref')
    sales_name = fields.Char(string='Sales Name')
    invent_site_id = fields.Char(string='Invent Site ID')
    invent_location_id = fields.Char(string='Invent Location ID')
    tax_group = fields.Char(string='Tax Group')
    is_executed = fields.Selection([
        ('No', 'No'),
        ('Yes', 'Yes')
    ], string='Is Executed', default='No')
    log = fields.Text(string='Log')
    line_ids = fields.One2many(
        'swa.sales.line.staging', 'table_id',
        string='Sales Lines')

    def action_create_sale_order(self):
        for rec in self:
            try:
                # Duplicate check
                existing_so = self.env['sale.order'].sudo().search([
                    ('name', '=', rec.sales_id)
                ], limit=1)
                if existing_so:
                    rec.write({
                        'is_executed': 'Yes',
                        'log': f"Skipped: Sale Order '{rec.sales_id}' already exists (ID: {existing_so.id})"
                    })
                    continue

                partner = self.env['res.partner'].sudo().search([
                    ('ref', '=', rec.cust_account)
                ], limit=1)
                if not partner:
                    rec.write({'log': f"Error: Partner with ref '{rec.cust_account}' not found. Sale Order not created."})
                    continue

                currency = self.env['res.currency'].sudo().search([
                    ('name', '=', rec.currency_code)
                ], limit=1) if rec.currency_code else False

                # Resolve company from staging setup
                setup = self.env['swa.staging.setup'].sudo().search([
                    ('invent_site_id', '=', rec.invent_site_id),
                    ('active', '=', True),
                ], limit=1)

                # Link any unlinked SalesLine records with matching sales_id
                unlinked = self.env['swa.sales.line.staging'].sudo().search([
                    ('sales_id', '=', rec.sales_id),
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
                        msg = f"Error: Item ID '{line.item_id}' not found. Sale Order not created." if line.item_id else "Error: Item ID is empty. Sale Order not created."
                        line.write({'log': msg})
                        all_lines_valid = False
                        continue
                    line_products.append((line, product))

                if not all_lines_valid:
                    rec.write({'log': f"Error: One or more products not found for Sales ID '{rec.sales_id}'. Sale Order not created."})
                    continue

                # All validation passed: create order
                order = self.env['sale.order'].sudo().create({
                    'name': rec.sales_id,
                    'partner_id': partner.id,
                    'partner_invoice_id': partner.id,
                    'partner_shipping_id': partner.id,
                    'currency_id': currency.id if currency else False,
                    'company_id': setup.company_id.id if setup else False,
                    'client_order_ref': rec.sales_id,
                })
                lines_created = 0

                for line, product in line_products:
                    uom = self.env['uom.uom'].sudo().search([
                        ('name', '=ilike', (line.sales_unit or '').strip())
                    ], limit=1) if line.sales_unit else False

                    self.env['sale.order.line'].sudo().create({
                        'order_id': order.id,
                        'product_id': product.id,
                        'product_uom_qty': line.sales_qty or 0,
                        'price_unit': line.sales_price or 0,
                        'product_uom': uom.id if uom else product.uom_id.id,
                        'sequence': int(line.line_num or 0),
                        'name': product.name,
                    })
                    line.write({
                        'is_executed': 'Yes',
                        'log': f"Success: Sale Order Line created (Order: {order.name})"
                    })
                    lines_created += 1

                order.action_confirm()
                rec.write({
                    'is_executed': 'Yes',
                    'log': f"Success: Sale Order created (ID: {order.id}, Name: {order.name}, State: sale) with {lines_created} line(s)"
                })

            except Exception as e:
                rec.write({'log': f"Error: {str(e)}"})
                _logger.error(f"SalesTableStaging {rec.id} action_create_sale_order error: {str(e)}")
