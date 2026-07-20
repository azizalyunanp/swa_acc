from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class SwaItemStaging(models.Model):
    _name = 'swa.item.staging'
    _description = 'Item Staging (AX 2012)'

    item_id = fields.Char(string='Item ID')
    item_name = fields.Char(string='Item Name')
    unit_id = fields.Char(string='Unit ID')
    type_item = fields.Char(string='Type Item')
    is_executed = fields.Selection([
        ('No', 'No'),
        ('Yes', 'Yes')
    ], string='Is Executed', default='No')
    log = fields.Text(string='Log')

    def action_create_product(self):
        for rec in self:
            try:
                existing = self.env['product.product'].sudo().search([
                    ('default_code', '=', rec.item_id)
                ], limit=1)
                if existing:
                    rec.write({
                        'is_executed': 'Yes',
                        'log': f"Skipped: Product with default_code '{rec.item_id}' already exists (ID: {existing.id})"
                    })
                    continue

                uom_id = self._get_or_create_uom(rec.unit_id) if rec.unit_id else False

                product_type = 'service' if rec.item_id and rec.item_id.startswith('80') else 'consu'

                product = self.env['product.product'].sudo().create({
                    'default_code': rec.item_id,
                    'name': rec.item_name or rec.item_id,
                    'uom_id': uom_id,
                    'uom_po_id': uom_id,
                    'type': product_type,
                })
                rec.write({
                    'is_executed': 'Yes',
                    'log': f"Success: Product created (ID: {product.id}, Name: {product.name})"
                })

            except Exception as e:
                rec.write({'log': f"Error: {str(e)}"})
                _logger.error(f"ItemStaging {rec.id} action_create_product error: {str(e)}")

    def _get_or_create_uom(self, unit_name):
        if not unit_name:
            return False
        uom = self.env['uom.uom'].sudo().search([
            ('name', '=ilike', unit_name.strip())
        ], limit=1)
        if uom:
            return uom.id
        uom = self.env['uom.uom'].sudo().create({
            'name': unit_name.upper(),
            'category_id': self.env.ref('uom.product_uom_categ_unit').id,
            'uom_type': 'reference',
            'factor': 1.0,
        })
        _logger.info(f"Created new UoM: {unit_name.upper()}")
        return uom.id
