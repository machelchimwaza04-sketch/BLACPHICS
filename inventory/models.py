"""
Production-Grade Inventory Transaction & Ledger System for Blacphics POS.

This system provides:
- Complete audit trail of all inventory movements
- Double-entry inventory accounting
- Stock reconciliation capabilities
- COGS calculation and inventory valuation
- Branch-level isolation and concurrency control
"""

from django.conf import settings
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from branches.models import Branch


class InventoryTransaction(models.Model):
    """
    Records all inventory movements with complete audit trail.
    This is the source of truth for all stock changes.
    """

    # Transaction Types
    TRANSACTION_TYPES = [
        ('purchase_receipt', 'Purchase Receipt'),
        ('sale', 'Sale'),
        ('adjustment', 'Stock Adjustment'),
        ('transfer_in', 'Transfer In'),
        ('transfer_out', 'Transfer Out'),
        ('return', 'Customer Return'),
        ('damage', 'Damage Write-off'),
        ('count', 'Physical Count'),
        ('reservation', 'Stock Reservation'),
        ('reservation_release', 'Reservation Release'),
    ]

    # Transaction Status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ]

    # Core Fields
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='inventory_transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    transaction_number = models.CharField(max_length=50, unique=True, editable=False)
    general_ledger_entry = models.ForeignKey(
        'finance.JournalEntry', on_delete=models.PROTECT, null=True, blank=True, related_name='inventory_transactions'
    )
    idempotency_key = models.CharField(max_length=255, null=True, blank=True, db_index=True)

    # Related Objects (nullable for adjustments)
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='inventory_transactions')
    variant = models.ForeignKey('products.ProductVariant', on_delete=models.PROTECT,
                               null=True, blank=True, related_name='inventory_transactions')

    # Related Business Objects
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True)
    purchase = models.ForeignKey('suppliers.Purchase', on_delete=models.SET_NULL, null=True, blank=True)
    adjustment = models.ForeignKey('inventory.StockAdjustment', on_delete=models.SET_NULL, null=True, blank=True)

    # Quantity Changes
    quantity_change = models.IntegerField(help_text='Positive for stock in, negative for stock out')
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Status and Audit
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)

    # User tracking
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_inventory_transactions')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                   related_name='approved_inventory_transactions')
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                    related_name='completed_inventory_transactions')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    # Calculated Fields
    @property
    def total_cost_value(self):
        """Total cost value of this transaction."""
        return abs(self.quantity_change) * self.unit_cost

    @property
    def total_sales_value(self):
        """Total sales value of this transaction."""
        return abs(self.quantity_change) * self.unit_price

    @property
    def is_stock_in(self):
        """True if this transaction increases stock."""
        return self.quantity_change > 0

    @property
    def is_stock_out(self):
        """True if this transaction decreases stock."""
        return self.quantity_change < 0

    # Database Constraints
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['branch', 'created_at']),
            models.Index(fields=['product', 'variant', 'created_at']),
            models.Index(fields=['transaction_type', 'status']),
            models.Index(fields=['transaction_number']),
        ]
        constraints = [
            models.CheckConstraint(
            condition=~models.Q(quantity_change=0), # <-- Change 'check' to 'condition'
            name='non_zero_quantity_change'
        )
        ]

    def __str__(self):
        return f"{self.transaction_number} - {self.transaction_type} ({self.quantity_change})"

    def clean(self):
        """Validate transaction business rules."""
        if self.status == 'completed' and not self.completed_at:
            raise ValidationError("Completed transactions must have completion timestamp")

        if self.transaction_type in ['adjustment', 'count'] and not self.adjustment:
            raise ValidationError("Adjustments and counts must reference a StockAdjustment")

        if self.transaction_type == 'sale' and not self.order:
            raise ValidationError("Sales must reference an Order")

        if self.transaction_type == 'purchase_receipt' and not self.purchase:
            raise ValidationError("Purchase receipts must reference a Purchase")

    def save(self, *args, **kwargs):
        """Auto-generate transaction number if not set."""
        if not self.transaction_number:
            self.transaction_number = self._generate_transaction_number()
        super().save(*args, **kwargs)

    def _generate_transaction_number(self):
        """Generate unique transaction number: INV-BRANCH-YYYYMMDD-XXXX"""
        from django.utils import timezone
        year_month_day = timezone.now().strftime('%Y%m%d')
        branch_code = self.branch.code

        # Atomically get next sequence number for this branch/day
        sequence = InventoryTransactionSequence.get_next_number(self.branch, timezone.now().date())

        return f"INV-{branch_code}-{year_month_day}-{sequence:04d}"


class InventoryTransactionSequence(models.Model):
    """
    Atomic sequence generator for inventory transaction numbers.
    """
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    date = models.DateField()
    next_number = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('branch', 'date')

    @classmethod
    @transaction.atomic
    def get_next_number(cls, branch, date):
        """Atomically get next sequence number for branch/date."""
        sequence, created = cls.objects.select_for_update().get_or_create(
            branch=branch,
            date=date,
            defaults={'next_number': 0}
        )
        sequence.next_number += 1
        sequence.save(update_fields=['next_number'])
        return sequence.next_number

    def __str__(self):
        return f"Sequence for {self.branch.code} on {self.date}"


class InventoryCostLayer(models.Model):
    """
    Inventory cost layer for FIFO and perpetual valuation.
    """
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='inventory_cost_layers')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='cost_layers')
    variant = models.ForeignKey('products.ProductVariant', on_delete=models.PROTECT,
                               null=True, blank=True, related_name='cost_layers')
    remaining_quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    source_transaction = models.ForeignKey(InventoryTransaction, on_delete=models.PROTECT, related_name='cost_layers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['branch', 'product', 'variant', 'created_at']),
        ]

    def __str__(self):
        product_name = self.variant.name if self.variant else self.product.name
        return f"{product_name} - {self.remaining_quantity} @ {self.unit_cost}"


class InventoryLedger(models.Model):
    """
    Double-entry inventory accounting ledger.
    Tracks inventory value changes with debit/credit entries.
    """

    # Entry Types
    ENTRY_TYPES = [
        ('debit', 'Debit'),   # Increases inventory value
        ('credit', 'Credit'), # Decreases inventory value
    ]

    # Account Types (Chart of Accounts for Inventory)
    ACCOUNT_TYPES = [
        ('inventory_asset', 'Inventory Asset'),
        ('cogs_expense', 'Cost of Goods Sold'),
        ('inventory_adjustment', 'Inventory Adjustment'),
        ('purchase_price_variance', 'Purchase Price Variance'),
        ('sales_revenue', 'Sales Revenue'),
        ('sales_discount', 'Sales Discount'),
    ]

    # Core Fields
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='inventory_ledger_entries')
    transaction = models.ForeignKey(InventoryTransaction, on_delete=models.PROTECT, related_name='ledger_entries')

    # Accounting Entry
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPES)
    account_type = models.CharField(max_length=25, choices=ACCOUNT_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    # Reference Data
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    variant = models.ForeignKey('products.ProductVariant', on_delete=models.PROTECT, null=True, blank=True)

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)

    # Database Constraints
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['branch', 'created_at']),
            models.Index(fields=['account_type', 'created_at']),
            models.Index(fields=['transaction']),
        ]

    def __str__(self):
        return f"{self.entry_type.title()} {self.amount} - {self.account_type}"

    def clean(self):
        """Validate ledger entry rules."""
        if self.amount <= 0:
            raise ValidationError("Ledger amounts must be positive")


class StockAdjustment(models.Model):
    """
    Manual stock adjustments with approval workflow.
    """

    # Adjustment Types
    ADJUSTMENT_TYPES = [
        ('physical_count', 'Physical Count'),
        ('damage', 'Damage/Loss'),
        ('theft', 'Theft'),
        ('correction', 'Data Correction'),
        ('transfer', 'Branch Transfer'),
        ('return_to_supplier', 'Return to Supplier'),
    ]

    # Status
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]

    # Core Fields
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='stock_adjustments')
    adjustment_type = models.CharField(max_length=20, choices=ADJUSTMENT_TYPES)
    adjustment_number = models.CharField(max_length=50, unique=True, editable=False)

    # Product Details
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='stock_adjustments')
    variant = models.ForeignKey('products.ProductVariant', on_delete=models.PROTECT,
                               null=True, blank=True, related_name='stock_adjustments')

    # Quantities
    system_quantity = models.PositiveIntegerField(help_text='Current system stock level')
    actual_quantity = models.PositiveIntegerField(help_text='Actual counted/physical quantity')
    adjustment_quantity = models.IntegerField(help_text='Adjustment amount (actual - system)')

    # Financial Impact
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_value_impact = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    # Status and Workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True)
    reason = models.TextField(help_text='Detailed reason for adjustment')

    # Related Objects
    related_purchase = models.ForeignKey('suppliers.Purchase', on_delete=models.SET_NULL, null=True, blank=True)
    transfer_to_branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='incoming_stock_adjustments')

    # User tracking
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_stock_adjustments')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                   related_name='approved_stock_adjustments')
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                    related_name='completed_stock_adjustments')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Database Constraints
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['branch', 'status']),
            models.Index(fields=['adjustment_type', 'status']),
            models.Index(fields=['adjustment_number']),
        ]

    def __str__(self):
        return f"{self.adjustment_number} - {self.adjustment_type}"

    def save(self, *args, **kwargs):
        """Auto-generate adjustment number and calculate values."""
        if not self.adjustment_number:
            self.adjustment_number = self._generate_adjustment_number()

        # Calculate adjustment quantity and value impact
        if self.actual_quantity is not None and self.system_quantity is not None:
            self.adjustment_quantity = self.actual_quantity - self.system_quantity
            self.total_value_impact = self.adjustment_quantity * self.unit_cost

        super().save(*args, **kwargs)

    def _generate_adjustment_number(self):
        """Generate unique adjustment number: ADJ-BRANCH-YYYYMMDD-XXXX"""
        from django.utils import timezone
        year_month_day = timezone.now().strftime('%Y%m%d')
        branch_code = self.branch.code

        # Atomically get next sequence number for this branch/day
        sequence = StockAdjustmentSequence.get_next_number(self.branch, timezone.now().date())

        return f"ADJ-{branch_code}-{year_month_day}-{sequence:04d}"

    @property
    def requires_approval(self):
        """Check if this adjustment requires approval."""
        # High-value adjustments or certain types require approval
        return (
            abs(self.total_value_impact) > Decimal('100.00') or
            self.adjustment_type in ['theft', 'damage']
        )

    def can_approve(self, user):
        """Check if user can approve this adjustment."""
        # Managers and admins can approve
        return user.is_staff or user.role in ['manager', 'admin']

    def approve(self, user):
        """Approve the adjustment."""
        if not self.can_approve(user):
            raise ValidationError("User does not have permission to approve adjustments")

        self.approved_by = user
        self.approved_at = timezone.now()
        self.status = 'approved'
        self.save()

    def reject(self, user, reason):
        """Reject the adjustment."""
        self.status = 'rejected'
        self.notes += f"\nRejected by {user.get_full_name()}: {reason}"
        self.save()

    def complete(self, user):
        """Complete the adjustment by creating inventory transaction."""
        from .services import InventoryService

        if self.status != 'approved':
            raise ValidationError("Only approved adjustments can be completed")

        # Create inventory transaction
        InventoryService.process_stock_adjustment(self, user)

        self.completed_by = user
        self.completed_at = timezone.now()
        self.status = 'completed'
        self.save()


class StockAdjustmentSequence(models.Model):
    """
    Atomic sequence generator for stock adjustment numbers.
    """
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    date = models.DateField()
    next_number = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('branch', 'date')

    @classmethod
    @transaction.atomic
    def get_next_number(cls, branch, date):
        """Atomically get next sequence number for branch/date."""
        sequence, created = cls.objects.select_for_update().get_or_create(
            branch=branch,
            date=date,
            defaults={'next_number': 0}
        )
        sequence.next_number += 1
        sequence.save(update_fields=['next_number'])
        return sequence.next_number

    def __str__(self):
        return f"Adjustment sequence for {self.branch.code} on {self.date}"


class InventorySnapshot(models.Model):
    """
    Periodic snapshots of inventory levels for reconciliation.
    """

    # Snapshot Types
    SNAPSHOT_TYPES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
        ('manual', 'Manual'),
    ]

    # Core Fields
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='inventory_snapshots')
    snapshot_type = models.CharField(max_length=20, choices=SNAPSHOT_TYPES)
    snapshot_date = models.DateTimeField(default=timezone.now)

    # Product Counts
    total_products = models.PositiveIntegerField()
    total_variants = models.PositiveIntegerField()
    total_units = models.PositiveIntegerField()
    total_value = models.DecimalField(max_digits=12, decimal_places=2)

    # Status Tracking
    low_stock_count = models.PositiveIntegerField()
    out_of_stock_count = models.PositiveIntegerField()

    # Audit
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    notes = models.TextField(blank=True)

    # Database Constraints
    class Meta:
        ordering = ['-snapshot_date']
        indexes = [
            models.Index(fields=['branch', 'snapshot_date']),
            models.Index(fields=['snapshot_type', 'snapshot_date']),
        ]
        unique_together = ('branch', 'snapshot_type', 'snapshot_date')

    def __str__(self):
        return f"{self.branch.name} {self.snapshot_type} snapshot - {self.snapshot_date.date()}"


class InventorySnapshotItem(models.Model):
    """
    Individual product/variant entries in inventory snapshots.
    """

    snapshot = models.ForeignKey(InventorySnapshot, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    variant = models.ForeignKey('products.ProductVariant', on_delete=models.PROTECT, null=True, blank=True)

    # Snapshot Data
    system_quantity = models.PositiveIntegerField()
    physical_quantity = models.PositiveIntegerField(null=True, blank=True)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    total_value = models.DecimalField(max_digits=12, decimal_places=2)

    # Variance Analysis
    variance_quantity = models.IntegerField(null=True, blank=True)
    variance_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ('snapshot', 'product', 'variant')

    def __str__(self):
        product_name = self.variant.name if self.variant else self.product.name
        return f"{product_name} - {self.system_quantity} units"