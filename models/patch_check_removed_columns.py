from odoo import models
from odoo.sql_db import Cursor
import logging

_logger = logging.getLogger(__name__)

_original_check_removed_columns = models.BaseModel._check_removed_columns


def _check_removed_columns_patched(self, log=False):
    if self._abstract:
        return
    # Check if table exists - if not, skip (new model, no columns to check)
    self._cr.execute(
        "SELECT 1 FROM pg_class WHERE relname=%s",
        [self._table]
    )
    if not self._cr.fetchone():
        return
    cols = [name for name, field in self._fields.items()
            if field.store and field.column_type]
    if not cols:
        return
    try:
        return _original_check_removed_columns(self, log=log)
    except Exception as e:
        if 'syntax error' in str(e).lower() and 'NOT IN' in str(e):
            _logger.warning(f"_check_removed_columns bypassed for {self._name}: empty NOT IN clause")
            self._cr.rollback()
            return
        raise


models.BaseModel._check_removed_columns = _check_removed_columns_patched
