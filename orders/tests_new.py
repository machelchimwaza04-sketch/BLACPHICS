"""
Production-grade tests for Order System.
Tests state management, concurrency, and business rules.
"""

import pytest
from django.test import TestCase, TransactionTestCase
from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from orders.models import Order, OrderItem, Payment, OrderNumberSequence
from orders.services import OrderService
from branches.models import Branch
from products.models import Product, ProductVariant
from django.contrib.auth import get_user_model

User = get_user_model()


class OrderStateMachineTest(TestCase):
    """Test order state transitions and immutability."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Test Branch", code="TB")
        self.user = User.objects.create_user(username="testuser", branch=self.branch)
        self.product = Product.objects.create(
            name="Test Product", price=Decimal('10.00'), stock=100
        )

    def test_order_creation(self):
        """Test basic order creation."""
        order = OrderService.create_order(
            branch=self.branch,
            created_by=self.user,
            transaction_type='quick_sale'
        )
        self.assertEqual(order.status, 'draft')
        self.assertTrue(order.order_number.startswith('TB-'))

    def test_state_machine_transitions(self):
        """Test valid state transitions."""
        order = OrderService.create_order(self.branch, self.user)
        OrderService.add_order_item(order, self.product, 1)

        # draft -> confirmed
        OrderService.confirm_order(order, self.user)
        self.assertEqual(order.status, 'confirmed')

        # confirmed -> completed
        OrderService.complete_order(order, self.user)
        self.assertEqual(order.status, 'completed')
        self.assertIsNotNone(order.completed_at)

    def test_invalid_transitions(self):
        """Test invalid state transitions are blocked."""
        order = OrderService.create_order(self.branch, self.user)

        # Cannot complete draft order
        with self.assertRaises(ValidationError):
            OrderService.complete_order(order, self.user)

        # Cannot cancel completed order
        OrderService.add_order_item(order, self.product, 1)
        OrderService.confirm_order(order, self.user)
        OrderService.complete_order(order, self.user)

        with self.assertRaises(ValidationError):
            OrderService.cancel_order(order, self.user)

    def test_immutability_after_completion(self):
        """Test orders become immutable after completion."""
        order = OrderService.create_order(self.branch, self.user)
        OrderService.add_order_item(order, self.product, 1)
        OrderService.confirm_order(order, self.user)
        OrderService.complete_order(order, self.user)

        # Cannot add items to completed order
        with self.assertRaises(ValidationError):
            OrderService.add_order_item(order, self.product, 1)

        # Cannot add payments to completed order
        with self.assertRaises(ValidationError):
            OrderService.add_payment(order, Decimal('10.00'), 'cash', self.user)


class OrderNumberGenerationTest(TransactionTestCase):
    """Test safe order number generation."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Test Branch", code="TB")

    def test_atomic_number_generation(self):
        """Test order numbers are unique under concurrent load."""
        def create_order_with_number():
            user = User.objects.create_user(
                username=f"user_{threading.current_thread().ident}",
                branch=self.branch
            )
            order = OrderService.create_order(self.branch, user)
            return order.order_number

        import threading
        numbers = []

        # Simulate concurrent order creation
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_order_with_number) for _ in range(50)]
            for future in futures:
                numbers.append(future.result())

        # All numbers should be unique
        self.assertEqual(len(numbers), len(set(numbers)))

        # Numbers should be sequential
        extracted_numbers = [int(n.split('-')[-1]) for n in numbers]
        extracted_numbers.sort()
        expected = list(range(1, 51))
        self.assertEqual(extracted_numbers, expected)


class StockManagementTest(TransactionTestCase):
    """Test stock management and race condition prevention."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Test Branch", code="TB")
        self.user = User.objects.create_user(username="testuser", branch=self.branch)
        self.product = Product.objects.create(
            name="Test Product", price=Decimal('10.00'), stock=10
        )

    def test_stock_deduction_on_completion(self):
        """Test stock is deducted only when order is completed."""
        order = OrderService.create_order(self.branch, self.user)
        OrderService.add_order_item(order, self.product, 5)

        # Stock should not be deducted yet
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

        # Confirm order (reserve stock for custom orders)
        OrderService.confirm_order(order, self.user)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)  # Still not deducted

        # Complete order (deduct stock)
        OrderService.complete_order(order, self.user)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_insufficient_stock_prevention(self):
        """Test orders cannot be created with insufficient stock."""
        order = OrderService.create_order(self.branch, self.user)

        # Try to add more items than available
        with self.assertRaises(ValidationError):
            OrderService.add_order_item(order, self.product, 15)

    def test_concurrent_stock_race_prevention(self):
        """Test stock race conditions are prevented."""
        def create_order_deducting_stock():
            user = User.objects.create_user(
                username=f"user_{threading.current_thread().ident}",
                branch=self.branch
            )
            order = OrderService.create_order(self.branch, user)
            try:
                OrderService.add_order_item(order, self.product, 1)
                OrderService.confirm_order(order, user)
                OrderService.complete_order(order, user)
                return True
            except ValidationError:
                return False

        import threading
        results = []

        # Try to create 15 orders (only 10 stock available)
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_order_deducting_stock) for _ in range(15)]
            for future in futures:
                results.append(future.result())

        # Only 10 should succeed
        successful_orders = sum(results)
        self.assertEqual(successful_orders, 10)

        # Stock should be zero
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)


class PaymentManagementTest(TestCase):
    """Test payment processing and validation."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Test Branch", code="TB")
        self.user = User.objects.create_user(username="testuser", branch=self.branch)
        self.product = Product.objects.create(
            name="Test Product", price=Decimal('10.00'), stock=100
        )

    def test_payment_calculation(self):
        """Test payment status calculation."""
        order = OrderService.create_order(self.branch, self.user)
        OrderService.add_order_item(order, self.product, 2)  # $20 total

        # Add partial payment
        OrderService.add_payment(order, Decimal('10.00'), 'cash', self.user)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'partial')
        self.assertEqual(order.amount_paid, Decimal('10.00'))
        self.assertEqual(order.balance_due, Decimal('10.00'))

        # Add remaining payment
        OrderService.add_payment(order, Decimal('10.00'), 'card', self.user)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'paid')
        self.assertEqual(order.amount_paid, Decimal('20.00'))
        self.assertEqual(order.balance_due, Decimal('0.00'))

    def test_overpayment_prevention(self):
        """Test overpayments are prevented."""
        order = OrderService.create_order(self.branch, self.user)
        OrderService.add_order_item(order, self.product, 1)  # $10 total

        # Try to overpay
        with self.assertRaises(ValidationError):
            OrderService.add_payment(order, Decimal('15.00'), 'cash', self.user)

    def test_no_payments_on_completed_orders(self):
        """Test payments cannot be added to completed orders."""
        order = OrderService.create_order(self.branch, self.user)
        OrderService.add_order_item(order, self.product, 1)
        OrderService.confirm_order(order, self.user)
        OrderService.complete_order(order, self.user)

        with self.assertRaises(ValidationError):
            OrderService.add_payment(order, Decimal('10.00'), 'cash', self.user)


class OrderIntegrationTest(TestCase):
    """Test complete order workflows."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Test Branch", code="TB")
        self.user = User.objects.create_user(username="testuser", branch=self.branch)
        self.product = Product.objects.create(
            name="Test Product", price=Decimal('10.00'), stock=100
        )

    def test_quick_sale_workflow(self):
        """Test complete quick sale workflow."""
        # Create order
        order = OrderService.create_order(
            branch=self.branch,
            created_by=self.user,
            transaction_type='quick_sale'
        )

        # Add items
        OrderService.add_order_item(order, self.product, 2)

        # Confirm (for quick sales, this might be automatic)
        OrderService.confirm_order(order, self.user)

        # Add payment
        OrderService.add_payment(order, Decimal('20.00'), 'cash', self.user)

        # Complete
        OrderService.complete_order(order, self.user)

        # Verify final state
        order.refresh_from_db()
        self.assertEqual(order.status, 'completed')
        self.assertEqual(order.payment_status, 'paid')
        self.assertEqual(order.amount_paid, Decimal('20.00'))

        # Verify stock deduction
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 98)

    def test_custom_order_workflow(self):
        """Test custom order workflow with stock reservation."""
        # Create custom order
        order = OrderService.create_order(
            branch=self.branch,
            created_by=self.user,
            transaction_type='custom_order'
        )

        # Add items (stock reserved on confirm)
        OrderService.add_order_item(order, self.product, 5)

        # Confirm (reserves stock)
        OrderService.confirm_order(order, self.user)

        # Stock should still be available (reserved, not deducted)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 100)

        # Complete (deducts stock)
        OrderService.complete_order(order, self.user)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 95)

    def test_order_cancellation(self):
        """Test order cancellation releases reserved stock."""
        order = OrderService.create_order(
            branch=self.branch,
            created_by=self.user,
            transaction_type='custom_order'
        )

        OrderService.add_order_item(order, self.product, 5)
        OrderService.confirm_order(order, self.user)  # Reserves stock

        # Cancel order
        OrderService.cancel_order(order, self.user)

        # Verify cancellation
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')
        self.assertIsNotNone(order.cancelled_at)

        # Stock should be released (no deduction occurred)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 100)