# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, time
from dateutil.relativedelta import relativedelta

from odoo import fields, models, _, api, Command
from odoo.exceptions import UserError
from odoo.tools import format_list

from datetime import timedelta

import logging

_logger = logging.getLogger(__name__)

class MrpWipAccountingLine(models.TransientModel):
    """
    WIP Accounting Line for individual journal entry lines.
    
    Each line represents either a debit or credit entry in the WIP
    journal entry, with proper account resolution from Product Category.
    """
    _name = 'mrp.account.wip.accounting.line'
    _description = 'WIP Accounting Entry Line'
    _order = 'sequence, id'
    # -------------------------------------------------------------------------
    # Fields Definition
    # -------------------------------------------------------------------------
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Determines the order of lines in the journal entry."
    )
    
    wip_accounting_id = fields.Many2one(
        comodel_name='mrp.account.wip.accounting',
        string='WIP Accounting Wizard',
        required=True,
        ondelete='cascade',
        help="Reference to the parent WIP accounting wizard."
    )
    
    mo_id = fields.Many2one(
        comodel_name='mrp.production',
        string='Manufacturing Order',
        help="Related manufacturing order for this line."
    )
    
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        related='mo_id.product_id',
        store=True,
        help="Finished product from the manufacturing order."
    )
    
    product_categ_id = fields.Many2one(
        comodel_name='product.category',
        string='Product Category',
        compute='_compute_product_categ_id',
        store=True,
        help="Product category used for account resolution."
    )
    
    label = fields.Char(
        string='Label',
        required=True,
        help="Description for the journal entry line."
    )
    
    line_type = fields.Selection(
        selection=[
            ('component', 'Component Value'),
            ('overhead', 'Overhead'),
            ('wip', 'WIP'),
            ('variance', 'Variance'),
            ('other', 'Other'),
        ],
        string='Line Type',
        default='other',
        required=True,
        help="Type of WIP entry line, used for automatic account resolution."
    )
    
    debit = fields.Monetary(
        string='Debit',
        currency_field='currency_id',
        default=0.0,
        help="Debit amount for this line."
    )
    
    credit = fields.Monetary(
        string='Credit',
        currency_field='currency_id',
        default=0.0,
        help="Credit amount for this line."
    )
    
    balance = fields.Monetary(
        string='Balance',
        compute='_compute_balance',
        store=True,
        currency_field='currency_id',
        help="Net balance (Debit - Credit)."
    )
    
    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Account',
        required=True,
        domain="[('deprecated', '=', False), ('company_id', '=', company_id)]",
        help="Account for this journal entry line."
    )
    
    resolved_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Resolved Account',
        compute='_compute_resolved_account_id',
        help="Account automatically resolved from Product Category based on line type."
    )
    
    account_source = fields.Selection(
        selection=[
            ('manual', 'Manual'),
            ('category', 'Product Category'),
            ('company', 'Company Default'),
            ('fallback', 'System Fallback'),
        ],
        string='Account Source',
        compute='_compute_account_source',
        help="Indicates where the account was resolved from."
    )
    
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        related='wip_accounting_id.company_id',
        store=True,
    )
    
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        related='company_id.currency_id',
        store=True,
    )
    
    analytic_distribution = fields.Json(
        string='Analytic Distribution',
        help="Analytic distribution for cost allocation."
    )
    
    note = fields.Text(
        string='Notes',
        help="Additional notes or remarks for this line."
    )
    # -------------------------------------------------------------------------
    # Compute Methods
    # -------------------------------------------------------------------------
    
    @api.depends('mo_id', 'mo_id.product_id', 'mo_id.product_id.categ_id')
    def _compute_product_categ_id(self):
        """Compute product category from manufacturing order."""
        for line in self:
            if line.mo_id and line.mo_id.product_id:
                line.product_categ_id = line.mo_id.product_id.categ_id
            else:
                line.product_categ_id = False
    
    @api.depends('debit', 'credit')
    def _compute_balance(self):
        """Compute balance as debit minus credit."""
        for line in self:
            line.balance = line.debit - line.credit
    
    @api.depends('line_type', 'product_categ_id', 'company_id')
    def _compute_resolved_account_id(self):
        """
        Automatically resolve account from Product Category based on line type.
        
        Resolution priority:
        1. Product Category specific account
        2. Company default account
        3. System fallback
        """
        for line in self:
            line.resolved_account_id = line._get_account_for_line_type()
    
    @api.depends('account_id', 'resolved_account_id', 'product_categ_id')
    def _compute_account_source(self):
        """Determine the source of the account."""
        for line in self:
            if not line.account_id:
                line.account_source = False
            elif line.product_categ_id and line.account_id == line.resolved_account_id:
                line.account_source = 'category'
            elif line.account_id == line._get_company_default_account():
                line.account_source = 'company'
            else:
                line.account_source = 'manual'
    # -------------------------------------------------------------------------
    # Account Resolution Methods
    # -------------------------------------------------------------------------
    
    def _get_account_for_line_type(self):
        """
        Get the appropriate account based on line type and product category.
        
        Returns:
            account.account: Resolved account record or False.
        """
        self.ensure_one()
        
        if not self.product_categ_id:
            return self._get_company_default_account()
        
        # Get accounts from specific product category
        accounts = self.product_categ_id.get_wip_accounts(self.company_id)
        
        # Map line type to account
        account_mapping = {
            'component': accounts.get('stock_valuation_account'),
            'overhead': accounts.get('overhead_account'),
            'wip': accounts.get('wip_account'),
            'variance': accounts.get('variance_account'),
            'other': accounts.get('stock_valuation_account'),
        }
        
        account = account_mapping.get(self.line_type)
        
        if not account:
            _logger.warning(
                "No account found for line type '%s' in category '%s'. "
                "Using company default.",
                self.line_type,
                self.product_categ_id.display_name
            )
            return self._get_company_default_account()
        
        return account
    
    def _get_company_default_account(self):
        """
        Get company default account as fallback.
        
        Returns:
            account.account: Company default account or False.
        """
        self.ensure_one()
        
        company = self.company_id or self.env.company
        
        if self.line_type == 'wip':
            return company.account_production_wip_account_id
        elif self.line_type == 'overhead':
            return company.account_production_wip_overhead_account_id
        
        # Generic fallback
        return False
    
    def action_resolve_account(self):
        """
        Action to resolve account from Product Category.
        Updates the account_id field with the resolved account.
        """
        for line in self:
            resolved = line._get_account_for_line_type()
            if resolved:
                line.account_id = resolved
            else:
                raise UserError(_(
                    "Could not resolve account for line type '%(type)s'. "
                    "Please configure the appropriate account in Product Category "
                    "or Company settings.",
                    type=dict(self._fields['line_type'].selection).get(line.line_type)
                ))
    # -------------------------------------------------------------------------
    # Onchange Methods
    # -------------------------------------------------------------------------
    
    @api.onchange('mo_id')
    def _onchange_mo_id(self):
        """Update product category and resolve account when MO changes."""
        if self.mo_id and self.mo_id.product_id:
            self.product_categ_id = self.mo_id.product_id.categ_id
            # Auto-resolve account based on line type
            if self.line_type and not self.account_id:
                self.account_id = self._get_account_for_line_type()
    
    @api.onchange('line_type')
    def _onchange_line_type(self):
        """Auto-resolve account when line type changes."""
        if self.line_type:
            resolved = self._get_account_for_line_type()
            if resolved:
                self.account_id = resolved
    
    @api.onchange('debit', 'credit')
    def _onchange_debit_credit(self):
        """Ensure debit and credit are not both non-zero."""
        if self.debit and self.credit:
            # Keep the last modified value
            return {
                'warning': {
                    'title': _("Warning"),
                    'message': _("A journal entry line cannot have both debit and credit values.")
                }
            }
    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------
    
    @api.constrains('debit', 'credit')
    def _check_debit_credit(self):
        """Validate that debit and credit are not both positive."""
        for line in self:
            if line.debit < 0 or line.credit < 0:
                raise ValidationError(_("Debit and credit amounts must be positive."))
            if line.debit and line.credit:
                raise ValidationError(_(
                    "A line cannot have both debit and credit amounts. "
                    "Line: %(label)s",
                    label=line.label
                ))
    
    @api.constrains('account_id', 'company_id')
    def _check_account_company(self):
        """Validate that account belongs to the same company."""
        for line in self:
            if line.account_id and line.company_id:
                if line.account_id.company_id and line.account_id.company_id != line.company_id:
                    raise ValidationError(_(
                        "Account '%(account)s' does not belong to company '%(company)s'.",
                        account=line.account_id.display_name,
                        company=line.company_id.display_name
                    ))
# =============================================================================
# MRP WIP ACCOUNTING WIZARD
# =============================================================================
class MrpWipAccounting(models.TransientModel):
    """
    Wizard for posting Manufacturing WIP (Work-In-Progress) account moves.
    
    This wizard creates journal entries to record:
    - Component value consumption (Credit: Stock Valuation, Debit: WIP)
    - Overhead allocation (Credit: Overhead Account, Debit: WIP)
    
    IMPORTANT: This version properly resolves accounts from the specific
    Product Category of each Manufacturing Order, rather than using global
    defaults from ir.property.
    
    Usage:
        1. Select Manufacturing Orders in 'progress', 'to_close', or 'confirmed' state
        2. Run the wizard
        3. Review and modify lines if needed
        4. Post the journal entry
    """
    _name = 'mrp.account.wip.accounting'
    _description = 'Wizard to post Manufacturing WIP account move'
    # -------------------------------------------------------------------------
    # Fields Definition
    # -------------------------------------------------------------------------
    
    date = fields.Date(
        string='Date',
        default=fields.Date.context_today,
        required=True,
        help="Date of the WIP journal entry."
    )
    
    reversal_date = fields.Date(
        string='Reversal Date',
        compute='_compute_reversal_date',
        store=True,
        readonly=False,
        required=True,
        help="Date for the reversal entry. Defaults to the day after the entry date."
    )
    
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Journal',
        required=True,
        domain="[('type', '=', 'general'), ('company_id', '=', company_id)]",
        help="Journal for posting WIP entries."
    )
    
    reference = fields.Char(
        string='Reference',
        help="Reference text for the journal entry."
    )
    
    line_ids = fields.One2many(
        comodel_name='mrp.account.wip.accounting.line',
        inverse_name='wip_accounting_id',
        string='WIP Accounting Lines',
        compute='_compute_line_ids',
        store=True,
        readonly=False,
        help="Individual lines for the WIP journal entry."
    )
    
    mo_ids = fields.Many2many(
        comodel_name='mrp.production',
        string='Manufacturing Orders',
        help="Selected manufacturing orders for WIP accounting."
    )
    
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )
    
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        related='company_id.currency_id',
    )
    
    total_debit = fields.Monetary(
        string='Total Debit',
        compute='_compute_totals',
        currency_field='currency_id',
    )
    
    total_credit = fields.Monetary(
        string='Total Credit',
        compute='_compute_totals',
        currency_field='currency_id',
    )
    
    is_balanced = fields.Boolean(
        string='Is Balanced',
        compute='_compute_totals',
        help="Indicates if debits equal credits."
    )
    
    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Journal Entry',
        readonly=True,
        help="Posted journal entry."
    )
    
    reversal_move_id = fields.Many2one(
        comodel_name='account.move',
        string='Reversal Entry',
        readonly=True,
        help="Reversal journal entry."
    )
    
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('posted', 'Posted'),
            ('reversed', 'Posted & Reversed'),
        ],
        string='State',
        default='draft',
        readonly=True,
    )
    # -------------------------------------------------------------------------
    # Default Get
    # -------------------------------------------------------------------------
    
    @api.model
    def default_get(self, fields_list):
        """
        Get default values for the wizard.
        
        Filters selected MOs to only include those in valid states
        and sets appropriate defaults for journal and reference.
        """
        res = super().default_get(fields_list)
        
        # Get and filter manufacturing orders
        active_ids = self.env.context.get('active_ids', [])
        productions = self.env['mrp.production'].browse(active_ids)
        
        # Only include MOs that are in valid WIP states
        valid_states = ['progress', 'to_close', 'confirmed']
        productions = productions.filtered(lambda mo: mo.state in valid_states)
        
        if not productions and active_ids:
            _logger.warning(
                "No valid Manufacturing Orders found. Selected IDs: %s. "
                "Only orders in states %s are valid for WIP accounting.",
                active_ids, valid_states
            )
        
        # Set journal from first MO's product category or company default
        if 'journal_id' in fields_list:
            journal = self._get_default_journal(productions)
            if journal:
                res['journal_id'] = journal.id
        
        # Set reference
        if 'reference' in fields_list:
            if productions:
                res['reference'] = _(
                    "Manufacturing WIP - %(orders_list)s",
                    orders_list=format_list(self.env, productions.mapped('name'))
                )
            else:
                res['reference'] = _("Manufacturing WIP - Manual Entry")
        
        # Set MO IDs
        if 'mo_ids' in fields_list:
            res['mo_ids'] = [Command.set(productions.ids)]
        
        return res
    
    def _get_default_journal(self, productions):
        """
        Get default journal for WIP entries.
        
        Priority:
        1. Journal from first MO's product category
        2. Company default stock journal
        3. First general journal found
        
        Args:
            productions: mrp.production recordset
            
        Returns:
            account.journal: Journal record or False
        """
        journal = False
        
        # Try from product category
        if productions:
            product_categ = productions[0].product_id.categ_id
            journal = product_categ.property_stock_journal
        
        # Fallback to ir.property default
        if not journal:
            ProductCategory = self.env['product.category']
            field = ProductCategory._fields.get('property_stock_journal')
            if field:
                journal = field.get_company_dependent_fallback(ProductCategory)
        
        # Fallback to any general journal
        if not journal:
            journal = self.env['account.journal'].search([
                ('type', '=', 'general'),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
        
        return journal
    # -------------------------------------------------------------------------
    # Compute Methods
    # -------------------------------------------------------------------------
    
    @api.depends('date')
    def _compute_reversal_date(self):
        """Compute reversal date as the day after entry date."""
        for wizard in self:
            if wizard.date:
                wizard.reversal_date = wizard.date + timedelta(days=1)
            else:
                wizard.reversal_date = fields.Date.context_today(wizard) + timedelta(days=1)
    
    @api.depends('mo_ids', 'date')
    def _compute_line_ids(self):
        """
        Compute WIP accounting lines based on selected MOs.
        
        Creates lines for:
        - Component value (consumed materials)
        - Overhead costs (labor, machine time, etc.)
        - WIP accumulation (debit)
        """
        for wizard in self:
            if not wizard.mo_ids:
                wizard.line_ids = [Command.clear()]
                continue
            
            line_vals = wizard._get_line_vals(wizard.mo_ids, wizard.date)
            wizard.line_ids = [Command.clear()] + line_vals
    
    @api.depends('line_ids.debit', 'line_ids.credit')
    def _compute_totals(self):
        """Compute total debit, credit, and balanced status."""
        for wizard in self:
            wizard.total_debit = sum(wizard.line_ids.mapped('debit'))
            wizard.total_credit = sum(wizard.line_ids.mapped('credit'))
            wizard.is_balanced = abs(wizard.total_debit - wizard.total_credit) < 0.01
    # -------------------------------------------------------------------------
    # Account Resolution Methods (FIXED!)
    # -------------------------------------------------------------------------
    
    def _get_accounts_from_category(self, productions):
        """
        Get all required accounts from the Product Category of the manufactured product.
        
        IMPORTANT: This method properly reads from the specific Product Category record,
        NOT from the global ir.property defaults. This ensures that when you update
        the category's account settings, the changes are reflected in WIP entries.
        
        Args:
            productions: mrp.production recordset
            
        Returns:
            dict: Dictionary with account IDs:
                - stock_valuation: Stock Valuation Account ID
                - stock_input: Stock Input Account ID  
                - stock_output: Stock Output Account ID
                - wip: WIP Account ID
                - overhead: Overhead Account ID
                - raw_material: Raw Material Account ID
        """
        if not productions:
            _logger.info("No productions provided, using fallback accounts")
            return self._get_fallback_accounts()
        
        # Get the first MO's finished product category
        # In multi-category scenarios, you may want to group by category
        first_mo = productions[0]
        product = first_mo.product_id
        
        if not product:
            _logger.warning("MO %s has no product, using fallback accounts", first_mo.name)
            return self._get_fallback_accounts()
        
        category = product.categ_id
        
        if not category:
            _logger.warning(
                "Product %s has no category, using fallback accounts",
                product.display_name
            )
            return self._get_fallback_accounts()
        
        # Ensure we read with the correct company context
        category = category.with_company(self.company_id or self.env.company)
        
        _logger.info(
            "Resolving accounts from Product Category: %s (ID: %s) for MO: %s",
            category.display_name, category.id, first_mo.name
        )
        
        # Get accounts from the specific category record
        accounts = {
            'stock_valuation': (
                category.property_stock_valuation_account_id.id
                if category.property_stock_valuation_account_id else False
            ),
            'stock_input': (
                category.property_stock_account_input_categ_id.id
                if category.property_stock_account_input_categ_id else False
            ),
            'stock_output': (
                category.property_stock_account_output_categ_id.id
                if category.property_stock_account_output_categ_id else False
            ),
            'wip': self._resolve_wip_account(category),
            'overhead': self._resolve_overhead_account(category),
            'raw_material': self._resolve_raw_material_account(category),
        }
        
        # Log resolved accounts for debugging
        _logger.debug("Resolved accounts: %s", accounts)
        
        # Validate required accounts
        self._validate_accounts(accounts, category)
        
        return accounts
    
    def _resolve_wip_account(self, category):
        """
        Resolve WIP account with fallback chain.
        
        Priority:
        1. Category's az_property_wip_account_id
        2. Company's account_production_wip_account_id
        
        Args:
            category: product.category record
            
        Returns:
            int: Account ID or False
        """
        # Priority 1: Category specific
        if hasattr(category, 'az_property_wip_account_id') and category.az_property_wip_account_id:
            _logger.debug("WIP account from category: %s", category.az_property_wip_account_id.code)
            return category.az_property_wip_account_id.id
        
        # Priority 2: Company default
        company = self.company_id or self.env.company
        if company.account_production_wip_account_id:
            _logger.debug("WIP account from company: %s", company.account_production_wip_account_id.code)
            return company.account_production_wip_account_id.id
        
        _logger.warning("No WIP account found for category %s", category.display_name)
        return False
    
    def _resolve_overhead_account(self, category):
        """
        Resolve overhead account with fallback chain.
        
        Priority:
        1. Category's az_property_overhead_account_id
        2. Company's account_production_wip_overhead_account_id
        3. Category's property_stock_account_production_cost_id
        4. Category's property_stock_account_input_categ_id
        
        Args:
            category: product.category record
            
        Returns:
            int: Account ID or False
        """
        # Priority 1: Category's custom overhead account
        if hasattr(category, 'az_property_overhead_account_id') and category.az_property_overhead_account_id:
            return category.az_property_overhead_account_id.id
        
        # Priority 2: Company default
        company = self.company_id or self.env.company
        if company.account_production_wip_overhead_account_id:
            return company.account_production_wip_overhead_account_id.id
        
        # Priority 3: Category's production cost account
        if category.property_stock_account_production_cost_id:
            return category.property_stock_account_production_cost_id.id
        
        # Priority 4: Category's stock input account
        if category.property_stock_account_input_categ_id:
            return category.property_stock_account_input_categ_id.id
        
        return False
    
    def _resolve_raw_material_account(self, category):
        """
        Resolve raw material account with fallback chain.
        
        Priority:
        1. Category's az_property_raw_material_account_id
        2. Category's property_stock_valuation_account_id
        
        Args:
            category: product.category record
            
        Returns:
            int: Account ID or False
        """
        # Priority 1: Category's custom raw material account
        if hasattr(category, 'az_property_raw_material_account_id') and category.az_property_raw_material_account_id:
            return category.az_property_raw_material_account_id.id
        
        # Priority 2: Stock valuation account
        if category.property_stock_valuation_account_id:
            return category.property_stock_valuation_account_id.id
        
        return False
    
    def _get_fallback_accounts(self):
        """
        Get fallback accounts from global ir.property defaults.
        
        This is only used when no Manufacturing Orders are selected.
        In normal operation, accounts should always be resolved from
        the specific Product Category.
        
        Returns:
            dict: Dictionary with account IDs
        """
        ProductCategory = self.env['product.category']
        company = self.company_id or self.env.company
        
        def get_field_fallback(field_name):
            """Helper to safely get company dependent fallback."""
            field = ProductCategory._fields.get(field_name)
            if field:
                result = field.get_company_dependent_fallback(ProductCategory)
                return result.id if result else False
            return False
        
        return {
            'stock_valuation': get_field_fallback('property_stock_valuation_account_id'),
            'stock_input': get_field_fallback('property_stock_account_input_categ_id'),
            'stock_output': get_field_fallback('property_stock_account_output_categ_id'),
            'wip': company.account_production_wip_account_id.id if company.account_production_wip_account_id else False,
            'overhead': company.account_production_wip_overhead_account_id.id if company.account_production_wip_overhead_account_id else False,
            'raw_material': get_field_fallback('property_stock_valuation_account_id'),
        }
    
    def _validate_accounts(self, accounts, category):
        """
        Validate that all required accounts are present.
        
        Args:
            accounts: dict with account IDs
            category: product.category record
            
        Raises:
            UserError: If required accounts are missing
        """
        missing = []
        
        if not accounts.get('stock_valuation'):
            missing.append(_("Stock Valuation Account"))
        if not accounts.get('wip'):
            missing.append(_("WIP Account"))
        if not accounts.get('overhead'):
            missing.append(_("Overhead Account"))
        
        if missing:
            raise UserError(_(
                "The following accounts are not configured for Product Category '%(category)s':\n\n"
                "%(missing)s\n\n"
                "Please configure these accounts in:\n"
                "Inventory > Configuration > Product Categories > %(category)s > Account Properties",
                category=category.display_name,
                missing="\n".join(f"• {m}" for m in missing)
            ))
    
    def _get_overhead_account(self, productions=False):
        """
        Get overhead account with proper resolution chain.
        
        DEPRECATED: Use _get_accounts_from_category() instead.
        Kept for backward compatibility.
        
        Args:
            productions: mrp.production recordset (optional)
            
        Returns:
            int: Account ID
        """
        _logger.warning(
            "_get_overhead_account() is deprecated. "
            "Use _get_accounts_from_category() instead."
        )
        
        company = self.company_id or self.env.company
        
        # Priority 1: Company setting
        if company.account_production_wip_overhead_account_id:
            return company.account_production_wip_overhead_account_id.id
        
        # Priority 2: From specific product category
        if productions:
            category = productions[0].product_id.categ_id.with_company(company)
            
            if hasattr(category, 'az_property_overhead_account_id') and category.az_property_overhead_account_id:
                return category.az_property_overhead_account_id.id
            
            if category.property_stock_account_production_cost_id:
                return category.property_stock_account_production_cost_id.id
            
            if category.property_stock_account_input_categ_id:
                return category.property_stock_account_input_categ_id.id
        
        # Priority 3: Global fallback
        ProductCategory = self.env['product.category']
        cop_field = ProductCategory._fields.get('property_stock_account_production_cost_id')
        if cop_field:
            cop_acc = cop_field.get_company_dependent_fallback(ProductCategory)
            if cop_acc:
                return cop_acc.id
        
        input_field = ProductCategory._fields.get('property_stock_account_input_categ_id')
        if input_field:
            input_acc = input_field.get_company_dependent_fallback(ProductCategory)
            if input_acc:
                return input_acc.id
        
        raise UserError(_("Could not determine overhead account. Please configure it in Company or Product Category settings."))
    # -------------------------------------------------------------------------
    # Line Value Calculation Methods
    # -------------------------------------------------------------------------
    
    def _get_line_vals(self, productions=False, date=False):
        """
        Calculate and return WIP accounting line values.
        
        This method calculates:
        1. Component Value: Sum of consumed raw material values
        2. Overhead Value: Labor and machine costs from work orders
        3. WIP Debit: Total WIP to be capitalized
        
        Args:
            productions: mrp.production recordset
            date: datetime or date for filtering consumed materials
            
        Returns:
            list: List of Command.create() tuples for line_ids
        """
        if not productions:
            productions = self.env['mrp.production']
        
        if not date:
            date = datetime.now().replace(hour=23, minute=59, second=59)
        elif isinstance(date, fields.date.__class__):
            # Convert date to datetime for comparison
            date = datetime.combine(date, datetime.max.time())
        
        # Calculate component value from consumed materials
        compo_value = self._calculate_component_value(productions, date)
        
        # Calculate overhead value from work orders
        overhead_value = self._calculate_overhead_value(productions, date)
        
        # Get accounts from Product Category (FIXED!)
        accounts = self._get_accounts_from_category(productions)
        
        # Build line values
        lines = []
        
        # Line 1: Credit Stock Valuation (Component Value)
        if compo_value:
            lines.append(Command.create({
                'sequence': 10,
                'label': _("WIP - Component Value"),
                'line_type': 'component',
                'credit': compo_value,
                'debit': 0.0,
                'account_id': accounts['stock_valuation'],
                'mo_id': productions[0].id if len(productions) == 1 else False,
            }))
        
        # Line 2: Credit Overhead Account
        if overhead_value:
            lines.append(Command.create({
                'sequence': 20,
                'label': _("WIP - Overhead"),
                'line_type': 'overhead',
                'credit': overhead_value,
                'debit': 0.0,
                'account_id': accounts['overhead'],
                'mo_id': productions[0].id if len(productions) == 1 else False,
            }))
        
        # Line 3: Debit WIP Account (Total)
        total_wip = compo_value + overhead_value
        if total_wip:
            lines.append(Command.create({
                'sequence': 30,
                'label': _(
                    "Manufacturing WIP - %(orders_list)s",
                    orders_list=(
                        format_list(self.env, productions.mapped('name'))
                        if productions else _("Manual Entry")
                    )
                ),
                'line_type': 'wip',
                'debit': total_wip,
                'credit': 0.0,
                'account_id': accounts['wip'],
                'mo_id': productions[0].id if len(productions) == 1 else False,
            }))
        
        return lines
    
    def _calculate_component_value(self, productions, date):
        """
        Calculate the total value of consumed components.
        
        Uses the product's standard price or lot-specific price if
        the product is lot-valuated.
        
        Args:
            productions: mrp.production recordset
            date: datetime or date cutoff for filtering moves
            
        Returns:
            float: Total component value
        """
        if not productions:
            return 0.0
        
        # =========================================================================
        # FIX: Normalize date for comparison
        # stock.move.line.date is a Datetime field, so we need to ensure
        # consistent comparison types
        # =========================================================================
        from datetime import datetime, time
        
        if isinstance(date, datetime):
            # Already datetime - use as-is
            compare_datetime = date
        else:
            # It's a date object - convert to datetime at end of day
            compare_datetime = datetime.combine(date, time.max)
        
        total_value = 0.0
        
        for ml in productions.move_raw_ids.move_line_ids:
            # Skip if not picked or no quantity
            if not ml.picked or not ml.quantity:
                continue
            
            # Skip if move line date is after our cutoff
            # FIX: ml.date is datetime, compare_datetime is also datetime now
            if ml.date and ml.date > compare_datetime:
                continue
            
            # Determine unit price
            product = ml.product_id
            if product.lot_valuated and ml.lot_id and ml.lot_id.standard_price:
                unit_price = ml.lot_id.standard_price
            else:
                unit_price = product.standard_price
            
            # Calculate line value
            line_value = ml.quantity_product_uom * unit_price
            total_value += line_value
            
            _logger.debug(
                "Component: %s, Qty: %s, Price: %s, Value: %s",
                product.display_name, ml.quantity_product_uom, unit_price, line_value
            )
        
        return total_value
    
    def _calculate_overhead_value(self, productions, date):
        """
        Calculate overhead value from work orders.
        
        Args:
            productions: mrp.production recordset
            date: datetime cutoff for filtering
            
        Returns:
            float: Total overhead value
        """
        if not productions or not productions.workorder_ids:
            return 0.0
        
        # Use workorder's _cal_cost method if available
        if hasattr(productions.workorder_ids, '_cal_cost'):
            return productions.workorder_ids._cal_cost(date)
        
        # Fallback: Calculate based on duration and workcenter costs
        total_overhead = 0.0
        
        for wo in productions.workorder_ids:
            if wo.state in ['done', 'progress']:
                # Get workcenter cost per hour
                cost_per_hour = wo.workcenter_id.costs_hour or 0.0
                
                # Get duration in hours
                duration_hours = wo.duration / 60.0 if wo.duration else 0.0
                
                # Calculate overhead
                overhead = duration_hours * cost_per_hour
                total_overhead += overhead
                
                _logger.debug(
                    "Work Order: %s, Duration: %s hrs, Cost/hr: %s, Overhead: %s",
                    wo.name, duration_hours, cost_per_hour, overhead
                )
        
        return total_overhead
    # -------------------------------------------------------------------------
    # Action Methods
    # -------------------------------------------------------------------------
    
    def action_post(self):
        """
        Post the WIP journal entry.
        
        Creates an account.move with the configured lines and posts it.
        
        Returns:
            dict: Action to view the created journal entry
        """
        self.ensure_one()
        
        # Validate
        if not self.line_ids:
            raise UserError(_("No lines to post. Please add at least one line."))
        
        if not self.is_balanced:
            raise UserError(_(
                "The journal entry is not balanced.\n"
                "Total Debit: %(debit)s\n"
                "Total Credit: %(credit)s",
                debit=self.total_debit,
                credit=self.total_credit
            ))
        
        # Prepare move values
        move_vals = self._prepare_move_vals()
        
        # Create and post the move
        move = self.env['account.move'].create(move_vals)
        move.action_post()
        
        # Update wizard
        self.write({
            'move_id': move.id,
            'state': 'posted',
        })
        
        # Link move to manufacturing orders
        self._link_move_to_productions(move)
        
        _logger.info(
            "Posted WIP journal entry %s for MOs: %s",
            move.name, self.mo_ids.mapped('name')
        )
        
        # Return action to view the move
        return {
            'type': 'ir.actions.act_window',
            'name': _('WIP Journal Entry'),
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_post_and_reverse(self):
        """
        Post the WIP journal entry and create a reversal entry.
        
        The reversal entry is dated according to the reversal_date field.
        
        Returns:
            dict: Action to view the created journal entries
        """
        self.ensure_one()
        
        # First post the original entry
        self.action_post()
        
        if not self.move_id:
            raise UserError(_("Failed to create the original journal entry."))
        
        # Create reversal
        reversal_wizard = self.env['account.move.reversal'].with_context(
            active_model='account.move',
            active_ids=[self.move_id.id],
        ).create({
            'date': self.reversal_date,
            'reason': _("WIP Reversal - %(ref)s", ref=self.reference or ''),
            'journal_id': self.journal_id.id,
        })
        
        reversal_action = reversal_wizard.reverse_moves()
        
        # Get the reversal move
        if reversal_action.get('res_id'):
            reversal_move = self.env['account.move'].browse(reversal_action['res_id'])
        elif reversal_action.get('domain'):
            reversal_move = self.env['account.move'].search(reversal_action['domain'], limit=1)
        else:
            reversal_move = False
        
        if reversal_move:
            self.write({
                'reversal_move_id': reversal_move.id,
                'state': 'reversed',
            })
        
        _logger.info(
            "Posted WIP entry %s and reversal %s",
            self.move_id.name,
            reversal_move.name if reversal_move else 'N/A'
        )
        
        # Return action to view both moves
        return {
            'type': 'ir.actions.act_window',
            'name': _('WIP Journal Entries'),
            'res_model': 'account.move',
            'domain': [('id', 'in', [self.move_id.id, reversal_move.id if reversal_move else 0])],
            'view_mode': 'tree,form',
            'target': 'current',
        }
    
    def action_refresh_lines(self):
        """
        Manually refresh/recalculate the WIP lines.
        
        Useful when MO data has changed after the wizard was opened.
        """
        self.ensure_one()
        self._compute_line_ids()
        return {'type': 'ir.actions.act_window_close'}
    
    def action_view_move(self):
        """View the posted journal entry."""
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No journal entry has been posted yet."))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entry'),
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    
    def _prepare_move_vals(self):
        """
        Prepare values for creating the account.move.
        
        Returns:
            dict: Values for account.move.create()
        """
        self.ensure_one()
        
        line_vals = []
        for line in self.line_ids:
            line_vals.append(Command.create({
                'name': line.label,
                'account_id': line.account_id.id,
                'debit': line.debit,
                'credit': line.credit,
                'analytic_distribution': line.analytic_distribution,
            }))
        
        return {
            'journal_id': self.journal_id.id,
            'date': self.date,
            'ref': self.reference,
            'move_type': 'entry',
            'line_ids': line_vals,
            'company_id': self.company_id.id,
        }
    
    def _link_move_to_productions(self, move):
        """
        Link the created journal entry to the manufacturing orders.
        
        This allows tracking WIP entries from the MO form.
        
        Args:
            move: account.move record
        """
        # If there's a field on MO to track WIP moves, link them here
        # Example:
        # if hasattr(self.mo_ids, 'wip_move_ids'):
        #     self.mo_ids.write({'wip_move_ids': [Command.link(move.id)]})
        
        # For now, just add the MO references to the move's narration
        if self.mo_ids:
            mo_names = ", ".join(self.mo_ids.mapped('name'))
            if move.narration:
                move.narration += f"\n\nRelated Manufacturing Orders: {mo_names}"
            else:
                move.narration = f"Related Manufacturing Orders: {mo_names}"
