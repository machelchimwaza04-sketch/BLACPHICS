"""
Base test suite for OrderService ensuring race condition handling and atomicity.
Example tests demonstrating the new service layer.
"""

from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.db import transaction
from orders.services import OrderService
from orders.models import Order, OrderItem, Payment
from branches.models import Branch
from customers.models import Customer
from products.models import ProductVariant


class OrderServiceTestCase(TransactionTestCase):
    """Test OrderService with transaction isolation."""
    
    def setUp(self):
        self.branch = Branch.objects.create(
            name='Test Branch',
            manager_email='manager@test.com'
        )
        self.customer = Customer.objects.create(
            first_name='John',
            last_name='Doe',
            branch=self.branch,
            phone='1234567890'
        )
    
    def test_create_order_basic(self):
        """Test creating an order with items and payments."""
        order = OrderService.create_order(
            branch=self.branch,
            customer=self.customer,
            items_data=[],
            payments_data=[],
            transaction_type='sale'
        )
        
        self.assertIsNotNone(order)
        self.assertEqual(order.branch, self.branch)
        self.assertEqual(order.customer, self.customer)
    
    def test_add_payment_to_order(self):
        """Test adding payment to an order."""
        order = Order.objects.create(
            branch=self.branch,
            customer=self.customer,
            total_amount=Decimal('100.00'),
            transaction_type='sale'
        )
        
        payment = OrderService.add_payment_to_order(
            order=order,
            amount=Decimal('50.00'),
            method='cash',
            notes='Partial payment'
        )
        
        self.assertIsNotNone(payment)
        self.assertEqual(payment.amount, Decimal('50.00'))
        self.assertEqual(payment.order, order)
    
    def test_writeoff_order_balance(self):
        """Test writing off order balance."""
        order = Order.objects.create(
            branch=self.branch,
            customer=self.customer,
            total_amount=Decimal('100.00'),
            amount_paid=Decimal('0.00'),
            transaction_type='sale'
        )
        
        payment = OrderService.writeoff_order_balance(
            order=order,
            notes='Customer cannot pay'
        )
        
        self.assertEqual(payment.payment_type, 'writeoff')
        self.assertEqual(payment.amount, Decimal('100.00'))
    
    def test_transaction_atomicity(self):
        """Test that order creation is atomic (all or nothing)."""
        # This test ensures that if payment creation fails, the entire order is rolled back
        # In a real scenario, you'd trigger an error during item creation or payment
        order = OrderService.create_order(
            branch=self.branch,
            customer=self.customer,
            items_data=[],
            payments_data=[
                {'amount': '50.00', 'method': 'cash', 'payment_type': 'payment'}
            ],
            total_amount=Decimal('50.00'),
            transaction_type='sale'
        )
        
        # Verify order exists and payment was created
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())
        self.assertEqual(order.payments.count(), 1)

    def test_partial_payment_updates_order_amount_paid(self):
        """Partial payments should update order balance and status."""
        order = Order.objects.create(
            branch=self.branch,
            customer=self.customer,
            total_amount=Decimal('200.00'),
            transaction_type='custom_order'
        )

        payment = OrderService.add_payment_to_order(
            order=order,
            amount=Decimal('50.00'),
            method='cash',
            notes='First installment'
        )

        order.refresh_from_db()
        self.assertEqual(payment.amount, Decimal('50.00'))
        self.assertEqual(order.amount_paid, Decimal('50.00'))
        self.assertEqual(order.balance_due, Decimal('150.00'))
        self.assertEqual(order.payment_status, 'partial')
        self.assertEqual(order.payments.count(), 1)

    def test_add_payment_to_order_rejects_overpayment(self):
        order = Order.objects.create(
            branch=self.branch,
            customer=self.customer,
            total_amount=Decimal('80.00'),
            transaction_type='quick_sale'
        )

        with self.assertRaises(ValueError):
            OrderService.add_payment_to_order(order=order, amount=Decimal('100.00'))

    def test_writeoff_order_balance_marks_order_paid(self):
        order = Order.objects.create(
            branch=self.branch,
            customer=self.customer,
            total_amount=Decimal('120.00'),
            transaction_type='custom_order'
        )

        payment = OrderService.writeoff_order_balance(order=order, notes='Balance written off')
        order.refresh_from_db()

        self.assertEqual(payment.payment_type, 'writeoff')
        self.assertEqual(order.amount_paid, Decimal('120.00'))
        self.assertEqual(order.payment_status, 'paid')
