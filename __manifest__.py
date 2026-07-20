# -*- coding: utf-8 -*-
{
    "name": "SWA Accounting",
    "summary": "SWA Accounting",
    "description": """
SWA Accounting
    """,
    "author": "SWA Accounting",
    "website": "https://www.swaaccounting.com",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Uncategorized",
    "version": "0.1",
    # any module necessary for this one to work correctly
    "depends": [
        "base",
        "stock",
        "account",
        "mrp",
        "stock_account",
        "base_accounting_kit",
        # "kiewel",
    ],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "data/az_giro_sequence.xml",
        "data/ir_cron_staging.xml",


        "views/views.xml",
        "views/templates.xml",
        'views/product_category_views.xml',
        "views/res_config_settings_views.xml",
        "views/mrp_production_views.xml",

        "views/accounting_menu_inherit.xml",

        ### MY CUSTOM ###
        "views/user_defined/az_giro_input_views.xml",
        "views/user_defined/az_api_received_data_views.xml",
        "views/staging/item_staging_views.xml",
        "views/staging/cust_vend_staging_views.xml",
        "views/staging/cust_invoice_jour_staging_views.xml",
        "views/staging/invent_trans_staging_views.xml",
        "views/staging/sales_table_staging_views.xml",
        "views/staging/vend_invoice_jour_staging_views.xml",
        "views/staging/purch_table_staging_views.xml",
        "views/staging/staging_setup_views.xml",

        "views/foh/setup/az_mapping_account_foh_views.xml",
        "views/foh/setup/az_mapping_item_foh_views.xml",
        "views/foh/setup/az_item_foh_ratio_views.xml",

        "views/foh/az_foh_calculation_wizard_views.xml",
        "views/foh/az_foh_calculation_views.xml",
        "views/foh/az_foh_item_cost_price_views.xml",
        "views/foh/az_foh_production_cost_views.xml",
        "views/foh/az_foh_production_price_views.xml",
        "views/foh/az_foh_cost_price_fg_views.xml",

        "views/trial_balance_views.xml",

        ### END ###
        
        "reports/az_foh_overview.xml",
    ],
    # only loaded in demonstration mode
    "demo": [
        "demo/demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "swa_acc/static/src/css/**/*",
            "swa_acc/static/src/js/foh_calculation_list_button.js",
            "swa_acc/static/src/xml/foh_calculation_list_button.xml",
            "swa_acc/static/src/js/foh_item_cost_price_list_button.js",
            "swa_acc/static/src/xml/foh_item_cost_price_list_button.xml",
            "swa_acc/static/src/js/foh_production_cost_list_button.js",
            "swa_acc/static/src/xml/foh_production_cost_list_button.xml",
            "swa_acc/static/src/js/foh_production_price_list_button.js",
            "swa_acc/static/src/xml/foh_production_price_list_button.xml",
            "swa_acc/static/src/js/foh_cost_price_fg_list_button.js",
            "swa_acc/static/src/xml/foh_cost_price_fg_list_button.xml",
        ],
    },
    "installable": True,
    "application": True,
}
