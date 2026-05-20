from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from branches.models import Branch, User
from customers.models import Customer


class Order(models.Model):
    """
    Production-grade Order model with strict state management.
    """

    # =========================
    # ORDER TYPES
    # =========================
    TRANSACTION_TYPE_CHOICES = [
        ('quick_sale', 'Quick Sale'),
        ('custom_order', 'Custom Order'),
    ]

    # =========================
    # ORDER STATUSES (STRICT STATE MACHINE)
    # =========================
    STATUS_CHOICES = [
        ('draft', 'Draft'),           # Can be modified
        ('confirmed', 'Confirmed'),   # Stock reserved, cannot modify items
        ('in_progress', 'In Progress'), # Being prepared
        ('ready', 'Ready'),           # Ready for pickup/delivery
        ('completed', 'Completed'),   # Final state - IMMUTABLE
        ('cancelled', 'Cancelled'),   # Final state - IMMUTABLE
    ]

    # =========================
    # PAYMENT STATUSES
    # =========================
    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
    ]

    # =========================
    # CORE FIELDS (IMMUTABLE AFTER COMPLETION)
    # =========================
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, null=True, blank=True)

    order_number = models.CharField(max_length=20, unique=True, editable=False)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)

    # Status - STRICT state machine enforced
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # =========================
    # FINANCIAL FIELDS (LOCKED AFTER COMPLETION)
    # =========================
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_reason = models.CharField(max_length=255, blank=True)

    # Audit trail for discounts
    discount_approved_by = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True,
        related_name='discount_approvals'
    )

    # =========================
    # PAYMENT TRACKING
    # =========================
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # =========================
    # METADATA
    # =========================
    notes = models.TextField(blank=True)
    estimated_completion = models.DateTimeField(null=True, blank=True)

    # Guest checkout fields
    guest_email = models.EmailField(blank=True)
    guest_phone = models.CharField(max_length=50, blank=True)
    guest_address = models.TextField(blank=True)

    # =========================
    # AUDIT TRAIL
    # =========================
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_orders')
    completed_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='completed_orders')
    cancelled_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='cancelled_orders')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    # =========================
    # DATABASE CONSTRAINTS
    # =========================
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['branch', 'status']),
            models.Index(fields=['branch', 'created_at']),
            models.Index(fields=['order_number']),
            models.Index(fields=['status', 'payment_status']),
        ]
        # Prevent multiple active orders with same number per branch
        constraints = [
            models.UniqueConstraint(
                fields=['branch', 'order_number'],
                name='unique_order_number_per_branch'
            )
        ]

    # =========================
    # PROPERTIES
    # =========================
    @property
    def is_completed(self):
        return self.status == 'completed'

    @property
    def is_cancelled(self):
        return self.status == 'cancelled'

    @property
    def is_final_state(self):
        return self.status in ['completed', 'cancelled']

    @property
    def balance_due(self):
        return self.discounted_total - self.amount_paid

    @property
    def discounted_total(self):
        return self.total_amount - self.discount_amount

    @property
    def is_quick_sale(self):
        return self.transaction_type == 'quick_sale'

    @property
    def is_custom_order(self):
        return self.transaction_type == 'custom_order'

    # =========================
    # VALIDATION METHODS
    # =========================
    def clean(self):
        """Validate order state transitions and business rules."""
        if self.is_final_state:
            # IMMUTABILITY: No changes allowed to completed/cancelled orders
            if self.pk:  # Existing order
                original = Order.objects.get(pk=self.pk)
                immutable_fields = [
                    'total_amount', 'discount_amount', 'branch', 'customer',
                    'transaction_type', 'order_number'
                ]
                for field in immutable_fields:
                    if getattr(self, field) != getattr(original, field):
                        raise ValidationError(f"Cannot modify {field} on {self.status} order")

        # Business rules
        if self.discount_amount > self.total_amount:
            raise ValidationError("Discount cannot exceed order total")

        if self.amount_paid < 0:
            raise ValidationError("Amount paid cannot be negative")

    def can_transition_to(self, new_status):
        """Validate state machine transitions."""
        valid_transitions = {
            'draft': ['confirmed', 'cancelled'],
            'confirmed': ['in_progress', 'cancelled'],
            'in_progress': ['ready', 'cancelled'],
            'ready': ['completed', 'cancelled'],
            'completed': [],  # Terminal state
            'cancelled': [],  # Terminal state
        }
        return new_status in valid_transitions.get(self.status, [])

    # =========================
    # BUSINESS METHODS (CALLED BY SERVICE LAYER ONLY)
    # =========================
    def _set_completed(self, user):
        """Internal method to complete order - IMMUTABLE after this."""
        if not self.can_transition_to('completed'):
            raise ValidationError(f"Cannot complete order in status: {self.status}")

        self.status = 'completed'
        self.completed_by = user
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_by', 'completed_at', 'updated_at'])

    def _set_cancelled(self, user):
        """Internal method to cancel order - IMMUTABLE after this."""
        if not self.can_transition_to('cancelled'):
            raise ValidationError(f"Cannot cancel order in status: {self.status}")

        self.status = 'cancelled'
        self.cancelled_by = user
        self.cancelled_at = timezone.now()
        self.save(update_fields=['status', 'cancelled_by', 'cancelled_at', 'updated_at'])

    def _update_payment_status(self):
        """Recalculate payment status based on payments."""
        total_paid = sum(p.amount for p in self.payments.all())

        if total_paid == 0:
            self.payment_status = 'unpaid'
        elif total_paid < self.discounted_total:
            self.payment_status = 'partial'
        else:
            self.payment_status = 'paid'

        self.amount_paid = total_paid
        self.save(update_fields=['payment_status', 'amount_paid', 'updated_at'])

    # =========================
    # STRING REPRESENTATION
    # =========================
    def __str__(self):
        return f"Order {self.order_number} ({self.status})"


class OrderItem(models.Model):
    """
    Order line items with locked pricing and stock validation.
    """

    # =========================
    # RELATIONSHIPS
    # =========================
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT)
    variant = models.ForeignKey('products.ProductVariant', on_delete=models.PROTECT, null=True, blank=True)

    # =========================
    # QUANTITY (LOCKED AFTER ORDER CONFIRMED)
    # =========================
    quantity = models.PositiveIntegerField()

    # =========================
    # PRICING (LOCKED AT CREATION TIME)
    # =========================
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # Original price
    override_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    override_reason = models.CharField(max_length=255, blank=True)

    # LOCKED FINAL PRICE - never changes after creation
    final_unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    # =========================
    # CUSTOMIZATION
    # =========================
    customization_details = models.TextField(blank=True)
    customization_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # =========================
    # STOCK SNAPSHOT (at time of order)
    # =========================
    stock_status_at_order = models.CharField(max_length=20, choices=[
        ('in_stock', 'In Stock'),
        ('low_stock', 'Low Stock'),
        ('out_of_stock', 'Out of Stock'),
    ])

    # =========================
    # AUDIT TRAIL
    # =========================
    created_at = models.DateTimeField(auto_now_add=True)

    # =========================
    # DATABASE CONSTRAINTS
    # =========================
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['order', 'product']),
        ]
        # Prevent duplicate products in same order
        constraints = [
            models.UniqueConstraint(
                fields=['order', 'product', 'variant'],
                name='unique_product_per_order'
            )
        ]

    # =========================
    # PROPERTIES
    # =========================
    @property
    def subtotal(self):
        """Calculate line item total - immutable after creation."""
        return (self.final_unit_price + self.customization_price) * self.quantity

    @property
    def is_customized(self):
        return bool(self.customization_details or self.customization_price > 0)

    # =========================
    # VALIDATION
    # =========================
    def clean(self):
        """Validate order item business rules."""
        if self.order.is_final_state:
            raise ValidationError("Cannot modify items on completed/cancelled orders")

        # Price validation
        if self.override_price and self.override_price < 0:
            raise ValidationError("Override price cannot be negative")

        if self.customization_price < 0:
            raise ValidationError("Customization price cannot be negative")

    def save(self, *args, **kwargs):
        """Lock final price on creation."""
        if not self.pk:  # New item
            self.final_unit_price = self.override_price if self.override_price is not None else self.unit_price

            # Snapshot stock status
            if self.variant:
                available = self.variant.available_quantity
                if available > 5:
                    self.stock_status_at_order = 'in_stock'
                elif available > 0:
                    self.stock_status_at_order = 'low_stock'
                else:
                    self.stock_status_at_order = 'out_of_stock'
            else:
                self.stock_status_at_order = 'in_stock'

        super().save(*args, **kwargs)

    # =========================
    # STRING REPRESENTATION
    # =========================
    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


class Payment(models.Model):
    """
    Payment records with strict validation and audit trail.
    """

    # =========================
    # PAYMENT METHODS
    # =========================
    METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('digital_wallet', 'Digital Wallet'),
        ('credit', 'Store Credit'),
    ]

    # =========================
    # PAYMENT TYPES
    # =========================
    TYPE_CHOICES = [
        ('payment', 'Payment'),
        ('refund', 'Refund'),
        ('writeoff', 'Write-off'),
        ('adjustment', 'Adjustment'),
    ]

    # =========================
    # RELATIONSHIPS
    # =========================
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')
    processed_by = models.ForeignKey(User, on_delete=models.PROTECT)

    # =========================
    # PAYMENT DETAILS
    # =========================
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    payment_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='payment')

    # =========================
    # TRANSACTION DETAILS
    # =========================
    transaction_id = models.CharField(max_length=100, blank=True)  # External payment processor ID
    card_last_four = models.CharField(max_length=4, blank=True)    # For card payments
    notes = models.TextField(blank=True)

    # =========================
    # AUDIT TRAIL
    # =========================
    created_at = models.DateTimeField(auto_now_add=True)

    # =========================
    # DATABASE CONSTRAINTS
    # =========================
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['order', 'created_at']),
            models.Index(fields=['method', 'payment_type']),
        ]

    # =========================
    # VALIDATION
    # =========================
    def clean(self):
        """Validate payment business rules."""
        if self.order.is_final_state and self.pk is None:
            raise ValidationError("Cannot add payments to completed/cancelled orders")

        if self.amount <= 0 and self.payment_type == 'payment':
            raise ValidationError("Payment amount must be positive")

        if self.amount >= 0 and self.payment_type == 'refund':
            raise ValidationError("Refund amount must be negative")

    # =========================
    # STRING REPRESENTATION
    # =========================
    def __str__(self):
        return f"{self.payment_type.title()} {self.amount} ({self.method})"


class OrderNumberSequence(models.Model):
    """
    Atomic order number generation per branch.
    Eliminates race conditions in order number generation.
    """

    branch = models.OneToOneField(Branch, on_delete=models.CASCADE, primary_key=True)
    current_number = models.PositiveIntegerField(default=0)

    # =========================
    # BUSINESS METHODS
    # =========================
    @classmethod
    @transaction.atomic
    def get_next_number(cls, branch):
        """Atomically get next order number for branch."""
        sequence, created = cls.objects.select_for_update().get_or_create(
            branch=branch,
            defaults={'current_number': 0}
        )
        sequence.current_number += 1
        sequence.save(update_fields=['current_number'])
        return sequence.current_number

    @classmethod
    def generate_order_number(cls, branch):
        """Generate formatted order number: BRANCH-YYYY-XXXXX"""
        from django.utils import timezone

        year = timezone.now().year
        number = cls.get_next_number(branch)
        return f"{branch.code}-{year}-{number:05d}"

    # =========================
    # STRING REPRESENTATION
    # =========================
    def __str__(self):
        return f"Order sequence for {self.branch.name}: {self.current_number}"