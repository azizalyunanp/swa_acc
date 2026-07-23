from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class SwaCustInvoiceJourStaging(models.Model):
    _name = 'swa.cust.invoice.jour.staging'
    _description = 'Customer Invoice Journal Staging (AX 2012)'

    invoice_id = fields.Char(string='Invoice ID')
    invoice_account = fields.Char(string='Invoice Account')
    incl_tax = fields.Char(string='Include Tax')
    currency = fields.Char(string='Currency')
    invoice_date = fields.Date(string='Invoice Date')
    tax_group = fields.Char(string='Tax Group')
    invoice_amount = fields.Float(string='Invoice Amount')
    invoice_amount_mst = fields.Float(string='Invoice Amount (MST)')
    tax_amount = fields.Float(string='Tax Amount')
    invent_site_id = fields.Char(string='Invent Site ID')
    invent_location_id = fields.Char(string='Invent Location ID')
    sales_id = fields.Char(string='Sales ID')
    is_executed = fields.Selection([
        ('No', 'No'),
        ('Yes', 'Yes')
    ], string='Is Executed', default='No')
    log = fields.Text(string='Log')
    line_ids = fields.One2many(
        'swa.cust.invoice.trans.staging', 'jour_id',
        string='Invoice Lines')

    def action_deliver_and_invoice(self):
        for rec in self:
            try:
                sale = self.env['sale.order'].sudo().search([
                    ('name', '=', rec.sales_id)
                ], limit=1)
                if not sale:
                    rec.write({'log': f"Error: Sale Order '{rec.sales_id}' not found."})
                    continue

                partner = self.env['res.partner'].sudo().search([
                    ('ref', '=', rec.invoice_account),
                    ('customer_rank', '>', 0),
                ], limit=1)
                if not partner:
                    rec.write({'log': f"Error: Customer with ref '{rec.invoice_account}' not found."})
                    continue

                pickings = sale.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
                if not pickings:
                    rec.write({'log': 'Warning: No pending pickings found for this sale order.'})
                    continue

                # Validate all products and accounts first
                line_data = []
                for line in rec.line_ids:
                    product = self.env['product.product'].sudo().search([
                        ('default_code', '=', line.item_id)
                    ], limit=1) if line.item_id else False
                    if not product:
                        msg = f"Error: Item ID '{line.item_id}' not found." if line.item_id else "Error: Item ID is empty."
                        line.write({'log': msg})
                        continue
                    account = product.property_account_income_id or product.categ_id.property_account_income_categ_id
                    if not account:
                        line.write({'log': f"Error: No income account for product '{product.default_code}'."})
                        continue
                    line_data.append((line, product, account))

                if not line_data:
                    rec.write({'log': 'Error: No valid invoice lines. Invoice not created.'})
                    continue

                # Auto-create warehouse
                for line in rec.line_ids:
                    if line.invent_location_id:
                        wh = self._get_or_create_warehouse(line.invent_location_id)

                # Resolve company from staging setup
                company = False
                if rec.invent_site_id:
                    setup = self.env['swa.staging.setup'].sudo().search([
                        ('invent_site_id', '=', rec.invent_site_id),
                        ('active', '=', True),
                    ], limit=1)
                    if setup:
                        company = setup.company_id

                company_ids = [company.id] if company else self.env.company.ids
                ctx = {'allowed_company_ids': company_ids}

                # Validate delivery FIRST (picking must succeed before invoice)
                for picking in pickings:
                    try:
                        picking.sudo().with_context(**ctx).action_confirm()
                        picking.sudo().with_context(**ctx).action_assign()
                        picking.sudo().with_context(skip_backorder=True, **ctx).button_validate()
                    except Exception as pick_err:
                        raise ValueError(f"Picking {picking.name} validation failed: {pick_err}")
                    picking.write({
                        'swa_receipt_reference': rec.invoice_id,
                        'company_id': company.id if company else picking.company_id.id,
                    })
                    if picking.state != 'done':
                        raise ValueError(f"Picking {picking.name} state is still '{picking.state}' after validation")

                # Create customer invoice
                invoice = self.env['account.move'].sudo().with_context(**ctx).create({
                    'partner_id': partner.id,
                    'move_type': 'out_invoice',
                    'name': rec.invoice_id,
                    'invoice_date': rec.invoice_date,
                    'invoice_origin': rec.sales_id or '',
                    'company_id': company.id if company else False,
                })

                # Link invoice to sale order via sale_line_id on each line
                so_lines_by_product = {l.product_id.id: l for l in sale.order_line} if sale else {}

                lines_created = 0
                for line, product, account in line_data:
                    aml_vals = {
                        'move_id': invoice.id,
                        'product_id': product.id,
                        'account_id': account.id,
                        'quantity': line.qty or 0,
                        'price_unit': line.purch_price or 0,
                        'name': product.name,
                    }
                    if sale and product.id in so_lines_by_product:
                        aml_vals['sale_line_ids'] = [(4, so_lines_by_product[product.id].id, False)]
                    self.env['account.move.line'].sudo().create(aml_vals)
                    line.write({
                        'is_executed': 'Yes',
                        'log': f'Success: Invoice line created (Invoice: {invoice.name})',
                    })
                    lines_created += 1

                # Post invoice
                invoice.sudo().with_context(**ctx).action_post()

                # Link invoice to delivery picking
                invoice.write({'picking_id': pickings[0].id})

                rec.write({
                    'is_executed': 'Yes',
                    'log': f"Success: Delivered & Invoiced (Picking: {pickings[0].name}, Invoice: {invoice.name}) with {lines_created} line(s)",
                })

            except Exception as e:
                rec.write({'log': f"Error: {str(e)}"})
                _logger.error(f"CustInvoiceJour {rec.id} action_deliver_and_invoice error: {str(e)}")

    def _get_or_create_warehouse(self, location_id):
        if not location_id:
            return False
        wh = self.env['stock.warehouse'].sudo().search([
            ('code', '=ilike', location_id.strip())
        ], limit=1)
        if not wh:
            company = self.env.company
            wh = self.env['stock.warehouse'].sudo().create({
                'name': location_id,
                'code': location_id,
                'company_id': company.id,
            })
            _logger.info(f"Created warehouse: {location_id} (ID: {wh.id})")
        return wh
