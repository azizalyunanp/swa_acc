# -*- coding: utf-8 -*-

# ── Patch: Fix Odoo 18 _check_removed_columns empty NOT IN () bug ───
from . import patch_check_removed_columns

# ── Core / general models ────────────────────────────────────────
from . import models
from . import account_move
from . import stock_warehouse
from . import product_category
from . import res_config_settings
from . import mrp_production
from . import mrp_wip_accounting
# ── Factory Overhead (FOH) models ────────────────────────────────
from . import foh
from . import user_defined
# ── API Data models ────────────────────────────────────────────────
from . import api_received_data
# ── AX 2012 Staging models ──────────────────────────────────────────
from . import staging

# ── Inherit / Extension models ──────────────────────────────────────
from . import stock_picking
from . import account_move
