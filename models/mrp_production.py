from odoo import models, fields, _
from odoo.exceptions import UserError

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    az_account_move_ids = fields.Many2many('account.move', string="Accounting Entries", copy=False)
    
    def button_mark_done(self):
        res = super(MrpProduction, self).button_mark_done()
        for production in self:
            if production.company_id.az_calculate_raf_pick_account_automate:
                production._create_raf_pick_entries()
        return res

    def action_view_az_account_moves(self):
        self.ensure_one()
        return {
            'name': _('Accounting Entries'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.az_account_move_ids.ids)],
            'context': {'create': False},
        }


    def _create_raf_pick_entries(self):
        self.ensure_one()
        
        # Determine Journal: Try to find a general journal or create a specific one? 
        # For now, pick the first journal of type 'general' for the company.
        journal = self.env['account.journal'].search([
            ('type', '=', 'general'), 
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        
        if not journal:
            raise UserError(_("Please define a General Journal for this company to use for Manufacturing Accounting automation."))

        move_lines = []
        
        # 1. Pick Entry (Raw Materials)
        # Debit WIP (Finished Good's Category) vs Credit Raw Material Account (Component's Category)
        
        wip_account = self.product_id.categ_id.az_property_wip_account_id
        if not wip_account:
            raise UserError(_("Please define a WIP Account for category: %s") % self.product_id.categ_id.name)

        # Aggregate raw material costs by account
        raw_material_credits = {} # {account_id: amount}
        total_raw_material_cost = 0.0

        for move in self.move_raw_ids:
            if move.state == 'done':
                # Use value from stock move? Or calculate?
                # Using move.stock_valuation_layer_ids.value would be best if available, but layers might be generated asynchronously or tricky.
                # Simple fallback: quantity * price_unit associated with the move or product cost.
                # Standard Odoo flow: the move itself generates entries. We are adding EXTRA entries.
                # Let's assume we take the value from the move directly if possible.
                # Using sum of stock.valuation.layer value is the most accurate real cost.
                
                move_cost = sum(move.sudo().stock_valuation_layer_ids.mapped('value')) 
                # Note: value is usually negative for outgoing moves (consumed). We need absolute value.
                move_cost = abs(move_cost)
                
                # If no valuation layer (e.g. non-automated valuation), fallback to quantity * cost
                if move_cost == 0:
                     move_cost = move.quantity * move.product_id.standard_price

                if move_cost > 0:
                    rm_account = move.product_id.categ_id.az_property_raw_material_account_id
                    if not rm_account:
                         raise UserError(_("Please define a Raw Material Account for category: %s") % move.product_id.categ_id.name)
                    
                    raw_material_credits[rm_account.id] = raw_material_credits.get(rm_account.id, 0.0) + move_cost
                    total_raw_material_cost += move_cost

        # Create Lines for Pick
        # Credit Raw Material Accounts
        for account_id, amount in raw_material_credits.items():
            move_lines.append((0, 0, {
                'account_id': account_id,
                'name': _('Raw Material Consumption - %s') % self.name,
                'debit': 0.0,
                'credit': amount,
            }))
        
        # Debit WIP Account (Total RM Cost)
        if total_raw_material_cost > 0:
            move_lines.append((0, 0, {
                'account_id': wip_account.id,
                'name': _('WIP - Material Consumption - %s') % self.name,
                'debit': total_raw_material_cost,
                'credit': 0.0,
            }))

        # 2. RAF Entry (Finished Goods)
        # Debit RAF Account (Finished Good's Category) vs Credit WIP (Finished Good's Category)
        
        raf_account = self.product_id.categ_id.az_property_raf_account_id
        if not raf_account:
             raise UserError(_("Please define a RAF Account for category: %s") % self.product_id.categ_id.name)
        
        # Calculate Finished Good Value
        total_finished_cost = 0.0
        for move in self.move_finished_ids:
             if move.state == 'done' and move.product_id == self.product_id:
                # Finished good moves have positive value
                move_cost = sum(move.sudo().stock_valuation_layer_ids.mapped('value'))
                if move_cost == 0:
                    move_cost = move.quantity * move.product_id.standard_price
                total_finished_cost += move_cost

        if total_finished_cost > 0:
            # Debit RAF
            move_lines.append((0, 0, {
                'account_id': raf_account.id,
                'name': _('Report as Finished - %s') % self.name,
                'debit': total_finished_cost,
                'credit': 0.0,
            }))
            # Credit WIP
            move_lines.append((0, 0, {
                'account_id': wip_account.id,
                'name': _('WIP - Finished Goods - %s') % self.name,
                'debit': 0.0,
                'credit': total_finished_cost,
            }))

        if move_lines:
            move_vals = {
                'journal_id': journal.id,
                'date': fields.Date.today(),
                'ref': self.name,
                'line_ids': move_lines,
                'move_type': 'entry',
            }
            move = self.env['account.move'].create(move_vals)
            self.az_account_move_ids = [(4, move.id)]

