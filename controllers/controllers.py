# -*- coding: utf-8 -*-
# from odoo import http


# class SwaAcc(http.Controller):
#     @http.route('/swa_acc/swa_acc', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/swa_acc/swa_acc/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('swa_acc.listing', {
#             'root': '/swa_acc/swa_acc',
#             'objects': http.request.env['swa_acc.swa_acc'].search([]),
#         })

#     @http.route('/swa_acc/swa_acc/objects/<model("swa_acc.swa_acc"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('swa_acc.object', {
#             'object': obj
#         })

