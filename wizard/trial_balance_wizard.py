# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class TrialBalanceWizard(models.TransientModel):
    _name = 'swa.trial.balance.wizard'
    _description = 'Trial Balance Wizard'
    # TransientModel records are temporary and cleaned up periodically.
    # However, they persist during the user's session until the vacuum cron job runs.
    # This persistence allows the wizard record (and its ID) to remain available
    # when the user navigates back from the history view to the results view,
    # or even back to the wizard form itself (if using breadcrumbs).


    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    date_from = fields.Date(
        string='Start Date',
        required=True
    )
    date_to = fields.Date(
        string='End Date',
        required=True
    )

    target_move = fields.Selection([
        ('posted', 'All Posted Entries'),
        ('all', 'All Entries')
    ], string='Target Moves', default='posted', required=True)
    line_ids = fields.One2many(
        'swa.trial.balance.line',
        'wizard_id',
        string='Trial Balance Lines'
    )
    show_accounts = fields.Selection([
        ('all', 'All Accounts'),
        ('movement', 'With Movements'),
        ('not_zero', 'Not Zero Balance')
    ], string='Show Accounts', default='all', required=True)



    def action_generate(self):
        self.ensure_one()
        # Clean up all previous lines for this user to avoid cache/duplicate issues on navigation
        self.env['swa.trial.balance.line'].search([('create_uid', '=', self.env.uid)]).unlink()
        
        domain = [
            ('company_id', '=', self.company_id.id)
        ]
        

        
        if self.date_from:
            domain.append(('date', '>=', self.date_from))
        if self.date_to:
            domain.append(('date', '<=', self.date_to))
        
        if self.target_move == 'posted':
            domain.append(('parent_state', '=', 'posted'))
        
        move_lines = self.env['account.move.line'].search(domain)
        
        account_data = {}
        for line in move_lines:
            acc_id = line.account_id.id
            if acc_id not in account_data:
                account_data[acc_id] = {
                    'account_id': line.account_id.id,
                    'code': line.account_id.code,
                    'name': line.account_id.name,
                    'debit': 0.0,
                    'credit': 0.0,
                }
            account_data[acc_id]['debit'] += line.debit
            account_data[acc_id]['credit'] += line.credit
        
        lines_to_create = []
        for acc_id, data in account_data.items():
            balance = data['debit'] - data['credit']
            
            if self.show_accounts == 'movement' and data['debit'] == 0 and data['credit'] == 0:
                continue
            if self.show_accounts == 'not_zero' and balance == 0:
                continue
            
            lines_to_create.append({
                'wizard_id': self.id,
                'account_id': data['account_id'],
                'debit': data['debit'],
                'credit': data['credit'],
                'balance': balance,
                'date_from': self.date_from,
                'date_to': self.date_to,
                'company_id': self.company_id.id,
                'target_move': self.target_move,
            })
        
        lines_to_create.sort(key=lambda x: x.get('account_id'))
        
        for line_vals in lines_to_create:
            self.env['swa.trial.balance.line'].create(line_vals)
        
        action = self.env["ir.actions.act_window"]._for_xml_id("swa_acc.action_trial_balance_result")
        # The 'domain' here relies on the wizard_id (self.id).
        # Since 'self' is a TransientModel record, it persists for some time in the DB.
        # When the user clicks "Back" from the History view, Odoo re-loads this action.
        # It finds the lines because they are still in the database (linked to this wizard_id)
        # and the wizard record itself allows this domain filter to be valid contextually.
        action['domain'] = [('wizard_id', '=', self.id)]
        action['context'] = {
            'default_date_from': self.date_from,
            'default_date_to': self.date_to,
        }
        return action


class TrialBalanceLine(models.TransientModel):
    _name = 'swa.trial.balance.line'
    _description = 'Trial Balance Line'

    wizard_id = fields.Many2one(
        'swa.trial.balance.wizard',
        string='Wizard'
    )
    account_id = fields.Many2one(
        'account.account',
        string='Account'
    )
    debit = fields.Monetary(
        string='Debit',
        currency_field='currency_id'
    )
    credit = fields.Monetary(
        string='Credit',
        currency_field='currency_id'
    )
    balance = fields.Monetary(
        string='Balance',
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='wizard_id.company_id.currency_id',
        string='Currency'
    )
    date_from = fields.Date(
        string='Date From'
    )
    date_to = fields.Date(
        string='Date To'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company'
    )
    target_move = fields.Selection([
        ('posted', 'All Posted Entries'),
        ('all', 'All Entries')
    ], string='Target Moves')

    def action_view_history(self):
        self.ensure_one()
        
        domain = [
            ('account_id', '=', self.account_id.id),
            ('company_id', '=', self.company_id.id)
        ]
        
        if self.date_from:
            domain.append(('date', '>=', self.date_from))
        if self.date_to:
            domain.append(('date', '<=', self.date_to))
        
        if self.target_move == 'posted':
            domain.append(('parent_state', '=', 'posted'))
        
        return {
            'name': _('Account Move Lines - %s') % self.account_id.display_name,
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': domain,
            'target': 'current',
            'context': {
                'search_default_groupby_date': 1,
            }
        }
