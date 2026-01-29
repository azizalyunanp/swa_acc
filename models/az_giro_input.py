# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AzGiroInput(models.Model):
    _name = 'az.giro.input'
    _description = 'Giro Input'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New'),
        tracking=True
    )
    
    partner_type = fields.Selection(
        [('customer', 'Customer'), ('vendor', 'Vendor')],
        string='Partner Type',
        required=True,
        default='vendor',
        tracking=True,
        states={'confirmed': [('readonly', True)], 'cancelled': [('readonly', True)]}
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
        tracking=True,
        states={'confirmed': [('readonly', True)], 'cancelled': [('readonly', True)]}
    )
    
    amount = fields.Monetary(
        string='Amount',
        required=True,
        tracking=True,
        states={'confirmed': [('readonly', True)], 'cancelled': [('readonly', True)]}
    )
    
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        states={'confirmed': [('readonly', True)], 'cancelled': [('readonly', True)]}
    )
    
    cheque_reference = fields.Char(
        string='Cheque Reference',
        tracking=True,
        states={'confirmed': [('readonly', True)], 'cancelled': [('readonly', True)]}
    )
    
    memo = fields.Text(
        string='Memo',
        tracking=True,
        states={'confirmed': [('readonly', True)], 'cancelled': [('readonly', True)]}
    )
    
    giro_account_id = fields.Many2one(
        'account.account',
        string='Giro Account',
        required=True,
        domain=[('account_type', 'not in', ['asset_receivable', 'liability_payable'])],
        tracking=True,
        states={'confirmed': [('readonly', True)], 'cancelled': [('readonly', True)]}
    )
    
    account_move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True,
        copy=False,
        tracking=True
    )
    
    state = fields.Selection(
        [('draft', 'Draft'), ('confirmed', 'Confirmed'), ('cancelled', 'Cancelled')],
        string='Status',
        required=True,
        readonly=True,
        copy=False,
        tracking=True,
        default='draft'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        readonly=True,
        default=lambda self: self.env.company
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        readonly=True,
        default=lambda self: self.env.company.currency_id
    )

    @api.onchange('partner_type')
    def _onchange_partner_type(self):
        """Reset partner when partner type changes"""
        self.partner_id = False
        return {
            'domain': {
                'partner_id': self._get_partner_domain()
            }
        }

    def _get_partner_domain(self):
        """Get domain for partner_id based on partner_type"""
        if self.partner_type == 'customer':
            return [('customer_rank', '>', 0)]
        elif self.partner_type == 'vendor':
            return [('supplier_rank', '>', 0)]
        return []

    @api.model
    def create(self, vals):
        """Override create to generate sequence"""
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('az.giro.input') or _('New')
        return super(AzGiroInput, self).create(vals)

    def action_confirm(self):
        """Confirm the giro and create journal entry"""
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Only draft giro can be confirmed.'))
            
            if not record.giro_account_id:
                raise ValidationError(_('Giro Account is required before confirmation.'))
            
            # Create journal entry
            move = record._create_account_move()
            
            # Update state and link to journal entry
            record.write({
                'state': 'confirmed',
                'account_move_id': move.id
            })
            
            # Post the journal entry
            move.action_post()
        
        return True

    def action_draft(self):
        """Reset to draft"""
        for record in self:
            if record.state == 'confirmed' and record.account_move_id:
                # Check if journal entry can be reset
                if record.account_move_id.state == 'posted':
                    raise UserError(_('Cannot reset to draft. The journal entry is already posted. Please cancel the journal entry first.'))
                # Delete the draft journal entry
                record.account_move_id.unlink()
            
            record.write({
                'state': 'draft',
                'account_move_id': False
            })
        return True

    def action_cancel(self):
        """Cancel the giro"""
        for record in self:
            if record.account_move_id and record.account_move_id.state == 'posted':
                raise UserError(_('Cannot cancel. Please reverse the journal entry first.'))
            record.write({'state': 'cancelled'})
        return True

    def button_open_journal_entry(self):
        """Open the journal entry form"""
        self.ensure_one()
        if not self.account_move_id:
            raise UserError(_('No journal entry found for this giro.'))
        
        return {
            'name': _('Journal Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.account_move_id.id,
            'views': [(False, 'form')],
            'target': 'current',
        }


    def _create_account_move(self):
        """Create journal entry for the giro"""
        self.ensure_one()
        
        # Get partner's payable or receivable account
        if self.partner_type == 'vendor':
            partner_account = self.partner_id.property_account_payable_id
            if not partner_account:
                raise ValidationError(_('Partner %s does not have a payable account configured.') % self.partner_id.name)
        else:  # customer
            partner_account = self.partner_id.property_account_receivable_id
            if not partner_account:
                raise ValidationError(_('Partner %s does not have a receivable account configured.') % self.partner_id.name)
        
        # Get default journal (first one available)
        journal = self.env['account.journal'].search([
            ('type', '=', 'general'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        
        if not journal:
            raise ValidationError(_('No general journal found for company %s.') % self.company_id.name)
        
        # Prepare move lines
        move_lines = []
        
        # Debit line: Giro Account
        debit_line = {
            'account_id': self.giro_account_id.id,
            'partner_id': self.partner_id.id,
            'name': self.cheque_reference or self.name,
            'debit': self.amount,
            'credit': 0.0,
            'date': self.date,
        }
        move_lines.append((0, 0, debit_line))
        
        # Credit line: Partner's Payable/Receivable Account
        credit_line = {
            'account_id': partner_account.id,
            'partner_id': self.partner_id.id,
            'name': self.cheque_reference or self.name,
            'debit': 0.0,
            'credit': self.amount,
            'date': self.date,
        }
        move_lines.append((0, 0, credit_line))
        
        # Create account move
        move_vals = {
            'journal_id': journal.id,
            'date': self.date,
            'ref': self.name,
            'line_ids': move_lines,
            'partner_id': self.partner_id.id,
        }
        
        move = self.env['account.move'].create(move_vals)
        return move

    def unlink(self):
        """Prevent deletion of confirmed giro"""
        for record in self:
            if record.state == 'confirmed':
                raise UserError(_('Cannot delete confirmed giro. Please cancel it first.'))
        return super(AzGiroInput, self).unlink()
