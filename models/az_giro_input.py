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
    
    journal_bank_id = fields.Many2one(
        'account.journal',
        string='Bank Journal',
        domain=[('type', '=', 'bank')],
        tracking=True,
        states={'confirmed': [('readonly', True)], 'cancelled': [('readonly', True)]}
    )
    
    bank_account_id = fields.Many2one(
        'account.account',
        string='Bank Account',
        related='journal_bank_id.default_account_id',
        readonly=True,
        store=True
    )
    
    clearing_move_id = fields.Many2one(
        'account.move',
        string='Clearing Journal Entry',
        readonly=True,
        copy=False,
        tracking=True
    )
    
    reverse_move_id = fields.Many2one(
        'account.move',
        string='Reverse Journal Entry',
        readonly=True,
        copy=False,
        tracking=True
    )
    
    reverse_clearing_move_id = fields.Many2one(
        'account.move',
        string='Reverse Clearing Entry',
        readonly=True,
        copy=False,
        tracking=True
    )
    
    is_cleared = fields.Boolean(
        string='Cleared',
        compute='_compute_is_cleared',
        store=True
    )
    
    is_reversed = fields.Boolean(
        string='Reversed',
        compute='_compute_is_reversed',
        store=True
    )
    
    is_clearing_reversed = fields.Boolean(
        string='Clearing Reversed',
        compute='_compute_is_clearing_reversed',
        store=True
    )
    
    state = fields.Selection(
        [('draft', 'Draft'), 
         ('confirmed', 'Confirmed'), 
         ('cleared', 'Cleared'), 
         ('clearing_reversed', 'Clearing Reversed'),
         ('reversed', 'Reversed'),
         ('cancelled', 'Cancelled')],
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

    @api.depends('clearing_move_id')
    def _compute_is_cleared(self):
        """Compute if giro has been cleared"""
        for record in self:
            record.is_cleared = bool(record.clearing_move_id)

    @api.depends('reverse_move_id')
    def _compute_is_reversed(self):
        """Compute if giro has been reversed"""
        for record in self:
            record.is_reversed = bool(record.reverse_move_id)

    @api.depends('reverse_clearing_move_id')
    def _compute_is_clearing_reversed(self):
        """Compute if clearing has been reversed"""
        for record in self:
            record.is_clearing_reversed = bool(record.reverse_clearing_move_id)


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
            # Check clearing entry first
            if record.clearing_move_id:
                if record.clearing_move_id.state == 'posted':
                    raise UserError(_('Cannot reset to draft. The clearing journal entry is already posted. Please cancel the clearing entry first.'))
                # Delete the draft clearing entry
                record.clearing_move_id.unlink()
            
            if record.state == 'confirmed' and record.account_move_id:
                # Check if journal entry can be reset
                if record.account_move_id.state == 'posted':
                    raise UserError(_('Cannot reset to draft. The journal entry is already posted. Please cancel the journal entry first.'))
                # Delete the draft journal entry
                record.account_move_id.unlink()
            
            record.write({
                'state': 'draft',
                'account_move_id': False,
                'clearing_move_id': False
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

    def action_clearing(self):
        """Create clearing journal entry for confirmed giro"""
        for record in self:
            # Validation
            if record.state != 'confirmed':
                raise UserError(_('Only confirmed giro can be cleared.'))
            
            if record.is_cleared:
                raise UserError(_('This giro has already been cleared.'))
            
            if not record.journal_bank_id:
                raise ValidationError(_('Bank Journal is required for clearing.'))
            
            if not record.bank_account_id:
                raise ValidationError(_('Bank Account is not configured in the selected Bank Journal.'))
            
            # Create clearing journal entry
            clearing_move = record._create_clearing_move()
            
            # Update record with clearing journal entry and set state to cleared
            record.write({
                'clearing_move_id': clearing_move.id,
                'state': 'cleared'
            })
            
            # Post the clearing journal entry
            clearing_move.action_post()
        
        return True

    def button_open_clearing_entry(self):
        """Open the clearing journal entry form"""
        self.ensure_one()
        if not self.clearing_move_id:
            raise UserError(_('No clearing journal entry found for this giro.'))
        
        return {
            'name': _('Clearing Journal Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.clearing_move_id.id,
            'views': [(False, 'form')],
            'target': 'current',
        }

    def action_reverse_giro(self):
        """Create reverse journal entry for giro"""
        for record in self:
            # Validation
            if record.state not in ['confirmed', 'cleared', 'clearing_reversed']:
                raise UserError(_('Only confirmed, cleared, or clearing reversed giro can be reversed.'))
            
            if not record.account_move_id:
                raise UserError(_('No journal entry found to reverse.'))
            
            if record.account_move_id.state != 'posted':
                raise UserError(_('Only posted journal entries can be reversed.'))
            
            if record.is_reversed:
                raise UserError(_('This giro has already been reversed.'))
            
            # Create reverse journal entry
            reverse_move = record._create_reverse_move(
                record.account_move_id,
                _('Reverse: %s') % record.name
            )
            
            # Update record with reverse journal entry and set state to reversed
            record.write({
                'reverse_move_id': reverse_move.id,
                'state': 'reversed'
            })
            
            # Post the reverse journal entry
            reverse_move.action_post()
        
        return True

    def action_reverse_clearing(self):
        """Create reverse clearing journal entry"""
        for record in self:
            # Validation
            if record.state not in ['cleared', 'reversed']:
                raise UserError(_('Only cleared or reversed giro can have clearing reversed.'))
            
            if not record.clearing_move_id:
                raise UserError(_('No clearing entry found to reverse.'))
            
            if record.clearing_move_id.state != 'posted':
                raise UserError(_('Only posted clearing entries can be reversed.'))
            
            if record.is_clearing_reversed:
                raise UserError(_('This clearing has already been reversed.'))
            
            # Create reverse clearing journal entry
            reverse_clearing_move = record._create_reverse_move(
                record.clearing_move_id,
                _('Reverse Clearing: %s') % record.name
            )
            
            # Update record with reverse clearing journal entry and set state
            record.write({
                'reverse_clearing_move_id': reverse_clearing_move.id,
                'state': 'clearing_reversed'
            })
            
            # Post the reverse clearing journal entry
            reverse_clearing_move.action_post()
        
        return True

    def button_open_reverse_entry(self):
        """Open the reverse journal entry form"""
        self.ensure_one()
        if not self.reverse_move_id:
            raise UserError(_('No reverse journal entry found for this giro.'))
        
        return {
            'name': _('Reverse Journal Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.reverse_move_id.id,
            'views': [(False, 'form')],
            'target': 'current',
        }

    def button_open_reverse_clearing_entry(self):
        """Open the reverse clearing journal entry form"""
        self.ensure_one()
        if not self.reverse_clearing_move_id:
            raise UserError(_('No reverse clearing entry found for this giro.'))
        
        return {
            'name': _('Reverse Clearing Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.reverse_clearing_move_id.id,
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

    def _create_clearing_move(self):
        """Create clearing journal entry"""
        self.ensure_one()
        
        # Get journal (use bank journal for clearing)
        journal = self.journal_bank_id
        
        if not journal:
            raise ValidationError(_('Bank Journal is required for clearing.'))
        
        # Prepare move lines
        move_lines = []
        
        # Debit line: Bank Account
        debit_line = {
            'account_id': self.bank_account_id.id,
            'partner_id': self.partner_id.id,
            'name': _('Clearing: %s') % (self.cheque_reference or self.name),
            'debit': self.amount,
            'credit': 0.0,
            'date': fields.Date.context_today(self),
        }
        move_lines.append((0, 0, debit_line))
        
        # Credit line: Giro Account
        credit_line = {
            'account_id': self.giro_account_id.id,
            'partner_id': self.partner_id.id,
            'name': _('Clearing: %s') % (self.cheque_reference or self.name),
            'debit': 0.0,
            'credit': self.amount,
            'date': fields.Date.context_today(self),
        }
        move_lines.append((0, 0, credit_line))
        
        # Create account move
        move_vals = {
            'journal_id': journal.id,
            'date': fields.Date.context_today(self),
            'ref': _('Clearing: %s') % self.name,
            'line_ids': move_lines,
            'partner_id': self.partner_id.id,
        }
        
        move = self.env['account.move'].create(move_vals)
        return move

    def _create_reverse_move(self, original_move, reverse_ref):
        """Create reverse journal entry from original move"""
        self.ensure_one()
        
        if not original_move:
            raise ValidationError(_('Original move is required for creating reverse entry.'))
        
        # Prepare reversed move lines
        move_lines = []
        
        for line in original_move.line_ids:
            # Reverse the debit and credit
            reversed_line = {
                'account_id': line.account_id.id,
                'partner_id': line.partner_id.id if line.partner_id else False,
                'name': line.name,
                'debit': line.credit,  # Swap debit and credit
                'credit': line.debit,
                'date': fields.Date.context_today(self),
            }
            move_lines.append((0, 0, reversed_line))
        
        # Create reverse account move
        move_vals = {
            'journal_id': original_move.journal_id.id,
            'date': fields.Date.context_today(self),
            'ref': reverse_ref,
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
            if record.is_cleared:
                raise UserError(_('Cannot delete cleared giro. Please reverse the clearing entry first.'))
        return super(AzGiroInput, self).unlink()
