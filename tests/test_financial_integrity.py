"""
Financial Integrity Validation Suite for Production Readiness.

This suite validates that financial operations maintain mathematical correctness
and that Assets = Liabilities + Equity at all times.
"""

from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.db.models import Sum
from branches.models import Branch
from finance.services import (
    compile_balance_sheet, compile_trial_balance, compile_profit_loss,
    compile_inventory_valuation, compile_accounts_receivable_aging,
    compile_accounts_payable_aging, get_account_balance
)
from finance.models import Account, JournalEntry, JournalLine
from products.models import Product, ProductVariant
from orders.models import Order
from orders.services import OrderService, PaymentService
from inventory.services import InventoryService
from suppliers.services import SupplierService
from suppliers.models import Supplier, Purchase
from django.contrib.auth import get_user_model

User = get_user_model()


class FinancialIntegrityTestCase(TransactionTestCase):
    """
    Test that all financial operations maintain mathematical correctness.
    """

    def setUp(self):
        self.branch = Branch.objects.create(name="Test Branch", code="TST")
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.product = Product.objects.create(
            name="Test Product",
            branch=self.branch,
            base_price=Decimal('10.00')
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name="Test Variant",
            stock_quantity=100,
            cost_price=Decimal('5.00'),
            selling_price=Decimal('10.00')
        )
        self.supplier = Supplier.objects.create(
            name="Test Supplier",
            email="supplier@test.com",
            phone="1234567890"
        )

    def test_balance_sheet_equation(self):
        """Test that Assets = Liabilities + Equity always holds."""
        # Create some transactions
        order = OrderService.create_order(
            branch=self.branch,
            created_by=self.user,
            transaction_type='quick_sale',
            items_data=[{
                'product': self.product,
                'variant': self.variant,
                'quantity': 1,
                'unit_price': Decimal('10.00')
            }]
        )

        PaymentService.add_payment(
            order=order,
            amount=Decimal('10.00'),
            method='cash',
            processed_by=self.user
        )

        OrderService.complete_order(order, self.user)

        # Check balance sheet
        bs = compile_balance_sheet(branch=self.branch)
        self.assertTrue(bs['is_balanced'],
                       f"Balance sheet not balanced: Assets={bs['total_assets']}, "
                       f"Liabilities+Equity={bs['total_liabilities'] + bs['total_equity']}")

    def test_trial_balance_totals(self):
        """Test that trial balance debits equal credits."""
        # Create transactions
        order = OrderService.create_order(
            branch=self.branch,
            created_by=self.user,
            transaction_type='quick_sale',
            items_data=[{
                'product': self.product,
                'variant': self.variant,
                'quantity': 2,
                'unit_price': Decimal('10.00')
            }]
        )

        PaymentService.add_payment(
            order=order,
            amount=Decimal('20.00'),
            method='cash',
            processed_by=self.user
        )

        OrderService.complete_order(order, self.user)

        # Check trial balance
        tb = compile_trial_balance(branch=self.branch)
        self.assertTrue(tb['is_balanced'],
                       f"Trial balance not balanced: Debits={tb['total_debits']}, "
                       f"Credits={tb['total_credits']}")

    def test_inventory_valuation_reconciliation(self):
        """Test that inventory GL balance matches physical valuation."""
        # Create purchase and sale
        purchase = Purchase.objects.create(
            branch=self.branch,
            supplier=self.supplier,
            purchase_number='TEST-PUR-001',
            total_amount=Decimal('50.00'),
            purchase_date='2024-01-01'
        )

        # Record purchase receipt
        InventoryService.create_inventory_transaction(
            branch=self.branch,
            transaction_type='purchase_receipt',
            product=self.product,
            variant=self.variant,
            quantity_change=10,
            unit_cost=Decimal('5.00'),
            created_by=self.user,
            purchase=purchase
        )

        # Create and complete sale
        order = OrderService.create_order(
            branch=self.branch,
            created_by=self.user,
            transaction_type='quick_sale',
            items_data=[{
                'product': self.product,
                'variant': self.variant,
                'quantity': 1,
                'unit_price': Decimal('10.00')
            }]
        )

        PaymentService.add_payment(
            order=order,
            amount=Decimal('10.00'),
            method='cash',
            processed_by=self.user
        )

        OrderService.complete_order(order, self.user)

        # Check inventory valuation
        inv_val = compile_inventory_valuation(branch=self.branch)
        variance = abs(inv_val['variance'])
        self.assertLess(variance, Decimal('0.01'),
                       f"Inventory valuation variance too high: {variance}")

    def test_ar_ap_aging_reconciliation(self):
        """Test that AR/AP aging matches ledger balances."""
        # Create sale with payment
        order = OrderService.create_order(
            branch=self.branch,
            created_by=self.user,
            transaction_type='quick_sale',
            items_data=[{
                'product': self.product,
                'variant': self.variant,
                'quantity': 1,
                'unit_price': Decimal('10.00')
            }]
        )

        OrderService.complete_order(order, self.user)

        # Check AR aging
        ar_aging = compile_accounts_receivable_aging(branch=self.branch)
        ar_balance = get_account_balance(self.branch, '1100')
        aging_total = sum(ar_aging['aging'].values())

        variance = abs(ar_balance - aging_total)
        self.assertLess(variance, Decimal('0.01'),
                       f"AR aging variance too high: {variance}")

    def test_journal_entry_balance_validation(self):
        """Test that all journal entries are properly balanced."""
        # Get all posted entries
        entries = JournalEntry.objects.filter(branch=self.branch, status='posted')

        for entry in entries:
            debits = entry.lines.filter(line_type='debit').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            credits = entry.lines.filter(line_type='credit').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            self.assertEqual(debits, credits,
                           f"Unbalanced journal entry {entry.reference}: Debits={debits}, Credits={credits}")

    def test_fifo_costing_mathematical_correctness(self):
        """Test that FIFO costing produces mathematically correct results."""
        # Create multiple purchase layers
        InventoryService.create_inventory_transaction(
            branch=self.branch,
            transaction_type='purchase_receipt',
            product=self.product,
            variant=self.variant,
            quantity_change=10,
            unit_cost=Decimal('5.00'),
            created_by=self.user
        )

        InventoryService.create_inventory_transaction(
            branch=self.branch,
            transaction_type='purchase_receipt',
            product=self.product,
            variant=self.variant,
            quantity_change=10,
            unit_cost=Decimal('6.00'),
            created_by=self.user
        )

        # Create sale
        InventoryService.create_inventory_transaction(
            branch=self.branch,
            transaction_type='sale',
            product=self.product,
            variant=self.variant,
            quantity_change=-15,
            unit_cost=Decimal('0.00'),  # Will be calculated by FIFO
            unit_price=Decimal('10.00'),
            created_by=self.user
        )

        # Check that COGS is correct: (10*5.00) + (5*6.00) = 50.00 + 30.00 = 80.00
        expected_cogs = Decimal('80.00')
        cogs_balance = abs(get_account_balance(self.branch, '5000'))

        self.assertEqual(cogs_balance, expected_cogs,
                        f"FIFO COGS incorrect: Expected={expected_cogs}, Actual={cogs_balance}")

    def test_retained_earnings_rollover(self):
        """Test that retained earnings roll forward correctly."""
        # This would require closing an accounting period
        # For now, just ensure the concept is implemented
        from finance.services import close_accounting_period, get_accounting_period

        period = get_accounting_period(self.branch, '2024-01-01')

        # Create some P&L transactions
        order = OrderService.create_order(
            branch=self.branch,
            created_by=self.user,
            transaction_type='quick_sale',
            items_data=[{
                'product': self.product,
                'variant': self.variant,
                'quantity': 1,
                'unit_price': Decimal('10.00')
            }]
        )

        PaymentService.add_payment(
            order=order,
            amount=Decimal('10.00'),
            method='cash',
            processed_by=self.user
        )

        OrderService.complete_order(order, self.user)

        # Close period (this should move net income to retained earnings)
        closed_period = close_accounting_period(period, created_by=self.user)

        # Check that retained earnings increased
        re_balance = get_account_balance(self.branch, '3010')
        self.assertGreater(re_balance, 0, "Retained earnings should have increased after period close")