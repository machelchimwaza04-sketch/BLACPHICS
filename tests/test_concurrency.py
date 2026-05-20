"""
Concurrency and Transaction Safety Tests for Production Readiness.

These tests validate that the system can handle concurrent operations safely
without race conditions, deadlocks, or data corruption.
"""

import pytest
from decimal import Decimal
from django.test import TransactionTestCase
from django.db import transaction
from django.core.exceptions import ValidationError
from concurrent.futures import ThreadPoolExecutor, as_completed
from branches.models import Branch
from products.models import Product, ProductVariant
from orders.models import Order
from orders.services import OrderService, PaymentService
from inventory.services import InventoryService
from suppliers.services import SupplierService
from suppliers.models import Supplier, Purchase
from finance.services import create_journal_entry, get_standard_account
from django.contrib.auth import get_user_model

User = get_user_model()


class ConcurrencyTestCase(TransactionTestCase):
    """
    Test concurrent operations to ensure thread safety and data integrity.
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

    def test_concurrent_inventory_operations(self):
        """Test concurrent inventory transactions don't cause race conditions."""
        def create_sale_transaction(thread_id):
            try:
                with transaction.atomic():
                    InventoryService.create_inventory_transaction(
                        branch=self.branch,
                        transaction_type='sale',
                        product=self.product,
                        variant=self.variant,
                        quantity_change=-1,
                        unit_cost=Decimal('5.00'),
                        unit_price=Decimal('10.00'),
                        created_by=self.user,
                        notes=f"Thread {thread_id} sale"
                    )
                return True
            except ValidationError:
                return False  # Expected when stock exhausted

        # Run 120 concurrent sales (more than available stock)
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_sale_transaction, i) for i in range(120)]
            results = [future.result() for future in as_completed(futures)]

        # Should have exactly 100 successful transactions
        successful = sum(1 for r in results if r)
        self.assertEqual(successful, 100)

        # Verify final stock
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 0)

    def test_concurrent_order_completions(self):
        """Test concurrent order completions don't double-process inventory."""
        orders = []
        for i in range(10):
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
            orders.append(order)

        def complete_order(order):
            try:
                OrderService.complete_order(order, self.user)
                return True
            except ValidationError:
                return False

        # Run concurrent completions
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(complete_order, order) for order in orders]
            results = [future.result() for future in as_completed(futures)]

        # Should have exactly 10 successful completions
        successful = sum(1 for r in results if r)
        self.assertEqual(successful, 10)

        # Verify final stock
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 90)

    def test_concurrent_payments_idempotency(self):
        """Test that concurrent identical payments are handled idempotently."""
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

        def add_payment(thread_id):
            try:
                PaymentService.add_payment(
                    order=order,
                    amount=Decimal('10.00'),
                    method='cash',
                    processed_by=self.user,
                    reference='TEST-REF-001',
                    idempotency_key='payment-test-001'
                )
                return True
            except ValidationError:
                return False

        # Run 5 concurrent identical payments
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(add_payment, i) for i in range(5)]
            results = [future.result() for future in as_completed(futures)]

        # Should have exactly 1 successful payment
        successful = sum(1 for r in results if r)
        self.assertEqual(successful, 1)

        # Verify payment amount
        order.refresh_from_db()
        self.assertEqual(order.amount_paid, Decimal('10.00'))

    def test_concurrent_supplier_payments(self):
        """Test concurrent supplier payments don't cause double-payment."""
        purchase = Purchase.objects.create(
            branch=self.branch,
            supplier=self.supplier,
            purchase_number='TEST-PUR-001',
            total_amount=Decimal('100.00'),
            purchase_date='2024-01-01'
        )

        def record_payment(thread_id):
            try:
                SupplierService.record_purchase_payment(
                    purchase=purchase,
                    amount=Decimal('50.00'),
                    processed_by=self.user,
                    reference=f'TEST-PAY-{thread_id}',
                    idempotency_key=f'purchase-payment-{thread_id}'
                )
                return True
            except ValidationError:
                return False

        # Run 3 concurrent payments
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(record_payment, i) for i in range(3)]
            results = [future.result() for future in as_completed(futures)]

        # Should have exactly 2 successful payments (100/50 = 2)
        successful = sum(1 for r in results if r)
        self.assertEqual(successful, 2)

        # Verify total paid
        purchase.refresh_from_db()
        self.assertEqual(purchase.amount_paid, Decimal('100.00'))

    def test_concurrent_journal_entries(self):
        """Test concurrent journal entries with same reference are idempotent."""
        cash = get_standard_account(self.branch, '1000')
        ar = get_standard_account(self.branch, '1100')

        def create_entry(thread_id):
            try:
                create_journal_entry(
                    branch=self.branch,
                    created_by=self.user,
                    reference='TEST-JE-001',
                    description='Test entry',
                    entry_date='2024-01-01',
                    lines=[
                        {'account': cash, 'line_type': 'debit', 'amount': '10.00'},
                        {'account': ar, 'line_type': 'credit', 'amount': '10.00'},
                    ],
                    idempotency_key='journal-test-001'
                )
                return True
            except ValidationError:
                return False

        # Run 5 concurrent identical entries
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_entry, i) for i in range(5)]
            results = [future.result() for future in as_completed(futures)]

        # Should have exactly 1 successful entry
        successful = sum(1 for r in results if r)
        self.assertEqual(successful, 1)

        # Verify journal entry exists
        from finance.models import JournalEntry
        entries = JournalEntry.objects.filter(branch=self.branch, reference='TEST-JE-001')
        self.assertEqual(entries.count(), 1)