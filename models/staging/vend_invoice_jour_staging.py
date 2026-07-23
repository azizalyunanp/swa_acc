from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class SwaVendInvoiceJourStaging(models.Model):
    _name = 'swa.vend.invoice.jour.staging'
    _description = 'Vendor Invoice Journal Staging (AX 2012)'

    invoice_id = fields.Char(string='Invoice ID')
    invoice_account = fields.Char(string='Invoice Account')
    incl_tax = fields.Char(string='Include Tax')
    internal_packing_slip = fields.Char(string='Internal Packing Slip')
    currency = fields.Char(string='Currency')
    invoice_date = fields.Char(string='Invoice Date')
    tax_group = fields.Char(string='Tax Group')
    invoice_amount = fields.Float(string='Invoice Amount')
    invoice_amount_mst = fields.Float(string='Invoice Amount (MST)')
    tax_amount = fields.Float(string='Tax Amount')
    invent_site_id = fields.Char(string='Invent Site ID')
    invent_location_id = fields.Char(string='Invent Location ID')
    purch_id = fields.Char(string='Purchase ID')
    is_executed = fields.Selection([
        ('No', 'No'),
        ('Yes', 'Yes')
    ], string='Is Executed', default='No')
    log = fields.Text(string='Log')
    line_ids = fields.One2many(
        'swa.vend.invoice.trans.staging', 'jour_id',
        string='Invoice Lines')

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

    def action_receive_and_bill(self):
        for rec in self:
            try:
                purchase = self.env['purchase.order'].sudo().search([
                    ('name', '=', rec.purch_id)
                ], limit=1)
                if not purchase:
                    rec.write({'log': f"Error: Purchase Order '{rec.purch_id}' not found."})
                    continue

                partner = self.env['res.partner'].sudo().search([
                    ('ref', '=', rec.invoice_account),
                    ('supplier_rank', '>', 0),
                ], limit=1)
                if not partner:
                    rec.write({'log': f"Error: Partner with ref '{rec.invoice_account}' not found."})
                    continue

                pickings = purchase.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel'))
                if not pickings:
                    rec.write({'log': 'Warning: No pending pickings found for this purchase order.'})
                    continue

                # Validate all products and accounts first (before any changes)
                line_data = []
                for line in rec.line_ids:
                    product = self.env['product.product'].sudo().search([
                        ('default_code', '=', line.item_id)
                    ], limit=1) if line.item_id else False
                    if not product:
                        msg = f"Error: Item ID '{line.item_id}' not found." if line.item_id else "Error: Item ID is empty."
                        line.write({'log': msg})
                        continue
                    account = product.property_account_expense_id or product.categ_id.property_account_expense_categ_id
                    if not account:
                        line.write({'log': f"Error: No expense account for product '{product.default_code}'."})
                        continue
                    line_data.append((line, product, account))

                if not line_data:
                    rec.write({'log': 'Error: No valid bill lines. Bill not created.'})
                    continue

                # Auto-create warehouse for each line's invent_location_id
                for line in rec.line_ids:
                    if line.invent_location_id:
                        self._get_or_create_warehouse(line.invent_location_id)

                # Resolve company from staging setup via invent_site_id
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

                # Validate picking FIRST (must succeed before bill)
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

                # Create vendor bill
                bill = self.env['account.move'].sudo().with_context(**ctx).create({
                    'partner_id': partner.id,
                    'move_type': 'in_invoice',
                    'name': rec.invoice_id,
                    'invoice_date': rec.invoice_date,
                    'invoice_origin': rec.purch_id or '',
                    'company_id': company.id if company else False,
                })

                if rec.purch_id:
                    po = self.env['purchase.order'].sudo().search([
                        ('name', '=', rec.purch_id)
                    ], limit=1)

                lines_created = 0
                po_lines_by_product = {l.product_id.id: l for l in po.order_line} if po else {}
                for line, product, account in line_data:
                    aml = self.env['account.move.line'].sudo().create({
                        'move_id': bill.id,
                        'product_id': product.id,
                        'account_id': account.id,
                        'quantity': line.qty or 0,
                        'price_unit': line.purch_price or 0,
                        'name': product.name,
                    })
                    # Link bill line to purchase order line by product
                    if po and product.id in po_lines_by_product:
                        aml.sudo().write({'purchase_line_id': po_lines_by_product[product.id].id})
                    line.write({
                        'is_executed': 'Yes',
                        'log': f'Success: Bill line created (Bill: {bill.name})',
                    })
                    lines_created += 1

                # Post the bill
                bill.sudo().with_context(**ctx).action_post()

                # Link bill to picking
                bill.write({'picking_id': pickings[0].id})

                rec.write({
                    'is_executed': 'Yes',
                    'log': f"Success: Received & Billed (Picking: {pickings[0].name}, Bill: {bill.name}) with {lines_created} line(s)",
                })

            except Exception as e:
                rec.write({'log': f"Error: {str(e)}"})
                _logger.error(f"VendInvoiceJour {rec.id} action_receive_and_bill error: {str(e)}")

