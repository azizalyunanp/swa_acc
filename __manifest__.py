# -*- coding: utf-8 -*-
{
    'name': "SWA Accounting",

    'summary': "SWA Accounting",

    'description': """
SWA Accounting
    """,

    'author': "SWA Accounting",
    'website': "https://www.swaaccounting.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'stock', 'account', 'mrp','stock_account'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/az_giro_sequence.xml',
        'views/views.xml',
        'views/templates.xml',
        'views/giro_input_views.xml',
        'views/product_category_views.xml',
        'views/res_config_settings_views.xml',
        'views/mrp_production_views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],

    "assets": {
            "web.assets_backend": [
                "swa_acc/static/src/css/**/*",
            ],
        },

    'installable': True,
    'application': True,
}

