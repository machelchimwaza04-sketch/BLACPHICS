"""
Comprehensive tests for Inventory Transaction & Ledger System.
"""

import pytest
from django.test import TestCase, TransactionTestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from branches.models import Branch
from products.models import Product, ProductVariant
from orders.models import Order, OrderItem
from suppliers.models import Purchase, PurchaseItem
from django.contrib.auth import get_user_model
from .models import (
    InventoryTransaction, InventoryLedger, StockAdjustment,
    InventorySnapshot, InventorySnapshotItem
)
from .services import InventoryService

User = get_user_model()


class InventoryTransactionTestCase(TestCase):
    """Test inventory transaction creation and validation."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Test Branch", code="TB")
        self.user = User.objects.create_user(username="testuser", branch=self.branch)
        self.product = Product.objects.create(
            name="Test Product", price=Decimal('10.00'), stock_quantity=100, branch=self.branch
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, size="M", color="Blue",
            stock_quantity=50, cost_price=Decimal('5.00')
        )

    def test_transaction_creation(self):
        """Test basic inventory transaction creation."""
        transaction = InventoryService.create_inventory_transaction(
            branch=self.branch,
            transaction_type='purchase_receipt',
            product=self.product,
            variant=self.variant,
            quantity_change=10,
            unit_cost=Decimal('5.00'),
            created_by=self.user
        )

        self.assertEqual(transaction.quantity_change, 10)
        self.assertEqual(transaction.transaction_type, 'purchase_receipt')
        self.assertEqual(transaction.status, 'completed')
        self.assertTrue(transaction.transaction_number.startswith('INV-TB-'))

        # Check stock was updated
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 60)

    def test_ledger_entries_created(self):
        """Test that ledger entries are created for transactions."""
        transaction = InventoryService.create_inventory_transaction(
            branch=self.branch,
            transaction_type='sale',
            product=self.product,
            variant=self.variant,
            quantity_change=-5,
            unit_cost=Decimal('5.00'),
            unit_price=Decimal('10.00'),
            created_by=self.user
        )

        # Should create debit (COGS) and credit (inventory) entries
        ledger_entries = InventoryLedger.objects.filter(transaction=transaction)
        self.assertEqual(ledger_entries.count(), 2)

        cogs_entry = ledger_entries.get(account_type='cogs_expense')
        self.assertEqual(cogs_entry.entry_type, 'debit')
        self.assertEqual(cogs_entry.amount, Decimal('25.00'))  # 5 * 5.00

        inventory_entry = ledger_entries.get(account_type='inventory_asset')
        self.assertEqual(inventory_entry.entry_type, 'credit')
        self.assertEqual(inventory_entry.amount, Decimal('25.00'))

    def test_insufficient_stock_prevention(self):
        """Test that outgoing transactions fail with insufficient stock."""
        with self.assertRaises(ValidationError):
            InventoryService.create_inventory_transaction(
                branch=self.branch,
                transaction_type='sale',
                product=self.product,
                variant=self.variant,
                quantity_change=-100,  # More than available
                unit_cost=Decimal('5.00'),
                created_by=self.user
            )


class StockAdjustmentTestCase(TestCase):
    """Test stock adjustment workflow."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Test Branch", code="TB")
        self.user = User.objects.create_user(username="testuser", branch=self.branch)
        self.manager = User.objects.create_user(username="manager", branch=self.branch)
        self.manager.is_staff = True
        self.manager.save()

        self.product = Product.objects.create(
            name="Test Product", price=Decimal('10.00'), stock_quantity=100, branch=self.branch
        )

    def test_adjustment_creation(self):
        """Test stock adjustment creation."""
        adjustment = InventoryService.create_stock_adjustment(
            branch=self.branch,
            adjustment_type='physical_count',
            product=self.product,
            system_quantity=100,
            actual_quantity=95,
            unit_cost=Decimal('5.00'),
            created_by=self.user,
            reason="Physical inventory count"
        )

        self.assertEqual(adjustment.adjustment_quantity, -5)
        self.assertEqual(adjustment.total_value_impact, Decimal('-25.00'))
        self.assertEqual(adjustment.status, 'approved')  # Auto-approved for small amounts

    def test_approval_workflow(self):
        """Test adjustment approval workflow."""
        # Create large adjustment requiring approval
        adjustment = StockAdjustment.objects.create(
            branch=self.branch,
            adjustment_type='damage',
            product=self.product,
            system_quantity=100,
            actual_quantity=50,  # Large adjustment
            unit_cost=Decimal('5.00'),
            reason="Damaged goods",
            created_by=self.user
        )

        self.assertEqual(adjustment.status, 'draft')
        self.assertTrue(adjustment.requires_approval)

        # Submit for approval
        adjustment.status = 'pending_approval'
        adjustment.save()

        # Approve
        adjustment.approve(self.manager)
        self.assertEqual(adjustment.status, 'approved')

        # Complete
        InventoryService.process_stock_adjustment(adjustment, self.user)
        self.assertEqual(adjustment.status, 'completed')

        # Check stock was adjusted
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 50)

    def test_adjustment_validation(self):
        """Test adjustment business rule validation."""
        # Try to complete unapproved adjustment
        adjustment = StockAdjustment.objects.create(
            branch=self.branch,
            adjustment_type='correction',
            product=self.product,
            system_quantity=100,
            actual_quantity=95,
            unit_cost=Decimal('5.00'),
            reason="Correction",
            created_by=self.user,
            status='draft'
        )

        with self.assertRaises(ValidationError):
            InventoryService.process_stock_adjustment(adjustment, self.user)


class InventorySnapshotTestCase(TestCase):
    """Test inventory snapshot creation and reconciliation."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Test Branch", code="TB")
        self.user = User.objects.create_user(username="testuser", branch=self.branch)

        self.product1 = Product.objects.create(
            name="Product 1", price=Decimal('10.00'), stock_quantity=100, branch=self.branch
        )
        self.product2 = Product.objects.create(
            name="Product 2", price=Decimal('20.00'), stock_quantity=50, branch=self.branch
        )

    def test_snapshot_creation(self):
        """Test inventory snapshot creation."""
        snapshot = InventoryService.create_inventory_snapshot(
            branch=self.branch,
            snapshot_type='manual',
            created_by=self.user
        )

        self.assertEqual(snapshot.total_products, 2)
        self.assertEqual(snapshot.total_units, 150)
        self.assertEqual(snapshot.total_value, Decimal('2000.00'))  # 100*10 + 50*20

        # Check snapshot items
        self.assertEqual(snapshot.items.count(), 2)

    def test_snapshot_with_physical_counts(self):
        """Test snapshot with physical count variances."""
        physical_counts = {
            f"product_{self.product1.id}": 95,  # 5 unit variance
            f"product_{self.product2.id}": 52,  # 2 unit variance
        }

        snapshot = InventoryService.create_inventory_snapshot(
            branch=self.branch,
            snapshot_type='manual',
            created_by=self.user,
            physical_counts=physical_counts
        )

        # Check variances
        item1 = snapshot.items.get(product=self.product1)
        self.assertEqual(item1.variance_quantity, -5)
        self.assertEqual(item1.variance_value, Decimal('-50.00'))  # Assuming 10 cost per unit

        item2 = snapshot.items.get(product=self.product2)
        self.assertEqual(item2.variance_quantity, 2)


class InventoryServiceTestCase(TransactionTestCase):
    """Test inventory service layer functionality."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Test Branch", code="TB")
        self.user = User.objects.create_user(username="testuser", branch=self.branch)
        self.product = Product.objects.create(
            name="Test Product", price=Decimal('10.00'), stock_quantity=100, branch=self.branch
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, size="M", color="Blue",
            stock_quantity=50, cost_price=Decimal('5.00')
        )

    def test_stock_update_atomicity(self):
        """Test that stock updates are atomic."""
        # This test would need concurrent execution to properly test
        # For now, just test basic atomicity
        initial_stock = self.variant.stock_quantity

        InventoryService.update_stock_level(
            product=self.product,
            variant=self.variant,
            quantity_change=10
        )

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, initial_stock + 10)

    def test_reservation_system(self):
        """Test stock reservation for orders."""
        # Reserve stock
        InventoryService.reserve_stock(self.product, self.variant, 10)

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.available_quantity, 40)  # 50 - 10

        # Release reservation
        InventoryService.release_reserved_stock(self.product, self.variant, 10)

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.available_quantity, 50)

    def test_inventory_valuation(self):
        """Test inventory valuation calculations."""
        valuation = InventoryService.get_inventory_valuation(self.branch)

        # Should include variant value
        expected_value = self.variant.stock_quantity * self.variant.cost_price
        self.assertEqual(valuation['physical_value'], expected_value)
        self.assertIn('ledger_inventory_value', valuation)
        self.assertIn('variance', valuation)

    def test_inventory_turnover(self):
        """Test inventory turnover calculations."""
        # Create some sales transactions
        for i in range(10):
            InventoryService.create_inventory_transaction(
                branch=self.branch,
                transaction_type='sale',
                product=self.product,
                variant=self.variant,
                quantity_change=-1,
                unit_cost=Decimal('5.00'),
                unit_price=Decimal('10.00'),
                created_by=self.user
            )

        turnover = InventoryService.get_inventory_turnover(self.branch, period_days=30)

        # Should have COGS and calculate turnover
        self.assertEqual(turnover['cogs'], Decimal('50.00'))  # 10 * 5.00
        self.assertGreater(turnover['turnover_ratio'], 0)


class OrderIntegrationTestCase(TestCase):
    """Test integration with order completion."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Test Branch", code="TB")
        self.user = User.objects.create_user(username="testuser", branch=self.branch)
        self.product = Product.objects.create(
            name="Test Product", price=Decimal('10.00'), stock_quantity=100, branch=self.branch
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, size="M", color="Blue",
            stock_quantity=50, cost_price=Decimal('5.00')
        )

    def test_order_completion_creates_transactions(self):
        """Test that completing an order creates inventory transactions."""
        # Create and complete an order
        order = Order.objects.create(
            branch=self.branch,
            order_number="TEST-001",
            transaction_type='quick_sale',
            created_by=self.user,
            status='draft'
        )

        OrderItem.objects.create(
            order=order,
            product=self.product,
            variant=self.variant,
            quantity=5,
            unit_price=Decimal('10.00'),
            final_unit_price=Decimal('10.00')
        )

        # Confirm and complete order
        from orders.services import OrderService as OrderSvc
        OrderSvc.confirm_order(order, self.user)
        OrderSvc.complete_order(order, self.user)

        # Check inventory transactions were created
        transactions = InventoryTransaction.objects.filter(order=order)
        self.assertEqual(transactions.count(), 1)

        transaction = transactions.first()
        self.assertEqual(transaction.quantity_change, -5)
        self.assertEqual(transaction.transaction_type, 'sale')

        # Check stock was reduced
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 45)


class PurchaseIntegrationTestCase(TestCase):
    """Test integration with purchase receipts."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Test Branch", code="TB")
        self.user = User.objects.create_user(username="testuser", branch=self.branch)
        self.product = Product.objects.create(
            name="Test Product", price=Decimal('10.00'), stock_quantity=0, branch=self.branch
        )

    def test_purchase_receipt_creates_transactions(self):
        """Test that receiving purchases creates inventory transactions."""
        # Create purchase
        purchase = Purchase.objects.create(
            branch=self.branch,
            supplier=None,  # Simplified for test
            purchase_number="PUR-001",
            status='ordered',
            total_amount=Decimal('50.00')
        )

        PurchaseItem.objects.create(
            purchase=purchase,
            product=self.product,
            quantity=10,
            unit_price=Decimal('5.00')
        )

        # Process receipt
        received_items = [{
            'purchase_item': purchase.items.first().id,
            'received_quantity': 10
        }]

        InventoryService.process_purchase_receipt(purchase, received_items, self.user)

        # Check inventory transactions were created
        transactions = InventoryTransaction.objects.filter(purchase=purchase)
        self.assertEqual(transactions.count(), 1)

        transaction = transactions.first()
        self.assertEqual(transaction.quantity_change, 10)
        self.assertEqual(transaction.transaction_type, 'purchase_receipt')

        # Check stock was increased
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)


class ConcurrencyTestCase(TransactionTestCase):
    """Test concurrency handling in inventory operations."""

    def setUp(self):
        self.branch = Branch.objects.create(name="Test Branch", code="TB")
        self.product = Product.objects.create(
            name="Test Product", price=Decimal('10.00'), stock_quantity=100, branch=self.branch
        )

    def test_concurrent_stock_updates(self):
        """Test that concurrent stock updates don't cause race conditions."""
        import threading
        from concurrent.futures import ThreadPoolExecutor

        results = []
        errors = []

        def update_stock(quantity_change, user_id):
            try:
                user = User.objects.create_user(f"user_{user_id}", branch=self.branch)
                InventoryService.create_inventory_transaction(
                    branch=self.branch,
                    transaction_type='adjustment',
                    product=self.product,
                    quantity_change=quantity_change,
                    unit_cost=Decimal('1.00'),
                    created_by=user
                )
                results.append(quantity_change)
            except Exception as e:
                errors.append(str(e))

        # Run concurrent updates
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(10):
                futures.append(executor.submit(update_stock, -1, i))

            for future in futures:
                future.result()

        # Check final stock
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 90)  # 100 - 10

        # Check transaction count
        transactions = InventoryTransaction.objects.filter(
            product=self.product,
            transaction_type='adjustment'
        )
        self.assertEqual(transactions.count(), 10)

        # Check no errors occurred
        self.assertEqual(len(errors), 0)