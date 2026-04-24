# -*- coding: utf-8 -*-

from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def write(self, vals):
        res = super(AccountMoveLine, self).write(vals)
        if 'partner_id' in vals:
            moves_to_update = self.mapped('move_id').filtered(
                lambda m: m.partner_id.id != vals['partner_id']
            )
            if moves_to_update:
                moves_to_update.write({'partner_id': vals['partner_id']})
        return res

    @api.model_create_multi
    def create(self, vals_list):
        lines = super(AccountMoveLine, self).create(vals_list)
        for line, vals in zip(lines, vals_list):
            if 'partner_id' in vals and line.move_id:
                if line.move_id.partner_id.id != vals['partner_id']:
                    line.move_id.partner_id = vals['partner_id']
        return lines

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        for move in self:
            partners = move.line_ids.mapped('partner_id')
            if partners:
                if move.partner_id != partners[0]:
                    move.partner_id = partners[0].id
        return super(AccountMove, self).action_post()
