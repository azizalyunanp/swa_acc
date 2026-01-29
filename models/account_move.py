# -*- coding: utf-8 -*-

from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def write(self, vals):
        res = super(AccountMoveLine, self).write(vals)
        if 'partner_id' in vals:
            for line in self:
                if line.move_id and line.move_id.partner_id.id != vals['partner_id']:
                    line.move_id.partner_id = vals['partner_id']
        return res

    @api.model
    def create(self, vals):
        res = super(AccountMoveLine, self).create(vals)
        if 'partner_id' in vals and res.move_id:
            if res.move_id.partner_id.id != vals['partner_id']:
                res.move_id.partner_id = vals['partner_id']
        return res

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        for move in self:
            partners = move.line_ids.mapped('partner_id')
            if partners:
                if move.partner_id != partners[0]:
                    move.partner_id = partners[0].id
        return super(AccountMove, self).action_post()
