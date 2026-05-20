from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.db import models, transaction, IntegrityError
from django.core.exceptions import ValidationError
from django.utils import timezone

from branches.models import Branch
from customers.models import Customer
from products.models import Product, ProductVariant, CustomizationService


class Order(models.Model):

    # =========================
    # CHOICES
    # =========================
    TRANSACTION_TYPE_CHOICES = [
        ('quick_sale', 'Quick Sale'),
        ('custom_order', 'Custom Order'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('ready', 'Ready for Pickup'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('deposit', 'Deposit Paid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Fully Paid'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('mobile_money', 'Mobile Money'),
        ('bank_transfer', 'Bank Transfer'),
    ]

    # =========================
    # CORE FIELDS
    # =========================
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='orders'
    )

    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='orders'
    )

    order_number = models.CharField(max_length=20, unique=True)

    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPE_CHOICES,
        default='quick_sale'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    # =========================
    # PAYMENT
    # =========================
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='unpaid'
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        blank=True
    )

    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_reason = models.CharField(max_length=255, blank=True)

    # 🔥 Audit trail
    discount_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='discount_approvals'
    )

    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # =========================
    # EXTRA
    # =========================
    notes = models.TextField(blank=True)
    estimated_completion = models.DateField(null=True, blank=True)

    guest_email = models.EmailField(blank=True)
    guest_phone = models.CharField(max_length=50, blank=True)
    guest_address = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_orders'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # =========================
    # REPRESENTATION
    # =========================
    def __str__(self):
        return f"Order {self.order_number} ({self.transaction_type})"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['transaction_type']),
        ]

    # =========================
    # PROPERTIES
    # =========================
    @property
    def discounted_total(self):
        return self.total_amount - self.discount_amount

    @property
    def balance_due(self):
        return self.discounted_total - self.amount_paid
    
    @property
    def change_due(self):
        overpaid = float(self.amount_paid) - float(self.discounted_total)
        return round(max(0, overpaid), 2)

    @property
    def credit_balance(self):
        overpaid = float(self.amount_paid) - float(self.discounted_total)
        return round(max(0, overpaid), 2)

    @property
    def is_guest_checkout(self):
        return self.customer is None and bool(self.guest_email or self.guest_phone or self.guest_address)

    @property
    def checkout_state(self):
        if self.status == 'pending':
            return 'order_received'
        if self.status in ['confirmed', 'in_progress', 'ready'] and self.payment_status != 'paid':
            return 'payment_processing'
        if self.status == 'completed' and self.payment_status == 'paid':
            return 'completed'
        return self.status

    def recalculate_payment_status(self):
        total_paid = Decimal('0.00')
        deposit_total = Decimal('0.00')

        for payment in self.payments.all():
            if payment.payment_type in ['payment', 'deposit', 'overpayment', 'writeoff']:
                total_paid += payment.amount
            elif payment.payment_type in ['refund', 'reversal']:
                total_paid -= abs(payment.amount)

            if payment.payment_type == 'deposit':
                deposit_total += payment.amount

        self.amount_paid = total_paid
        self.deposit_amount = deposit_total
        self.update_payment_status()
        self.save(update_fields=['amount_paid', 'deposit_amount', 'payment_status'])

    @classmethod
    def generate_order_number(cls, branch):
        """
        Generate a unique auto-incrementing order number per branch using the
        atomic branch sequence generator.
        """
        if isinstance(branch, int):
            branch = Branch.objects.get(pk=branch)

        return OrderNumberSequence.generate_order_number(branch)

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = OrderNumberSequence.generate_order_number(self.branch)

        for attempt in range(5):
            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)
                return
            except IntegrityError as exc:
                if 'order_number' not in str(exc).lower() or attempt == 4:
                    raise
                self.order_number = OrderNumberSequence.generate_order_number(self.branch)

    @property
    def is_quick_sale(self):
        return self.transaction_type == 'quick_sale'

    @property
    def is_custom_order(self):
        return self.transaction_type == 'custom_order'

    # =========================
    # PAYMENT LOGIC
    # =========================
    def update_payment_status(self):
        if self.amount_paid == 0:
            self.payment_status = 'unpaid'
        elif self.amount_paid < self.discounted_total:
            if self.deposit_amount > 0:
                self.payment_status = 'deposit'
            else:
                self.payment_status = 'partial'
        else:
            self.payment_status = 'paid'

    def apply_discount(self, amount, reason='', approved_by=None):
        if amount < 0:
            raise ValidationError('Discount amount cannot be negative.')
        if amount > self.total_amount:
            raise ValidationError('Discount cannot exceed order total.')
        if self.amount_paid > 0:
            raise ValidationError(
                'Cannot apply or modify discount after payments have been recorded.'
            )
        self.discount_amount = amount
        self.discount_reason = reason
        self.discount_approved_by = approved_by
        self.save(update_fields=['discount_amount', 'discount_reason', 'discount_approved_by'])

    def reserve_stock(self, ttl_hours=4):
        """
        DEPRECATED: Use OrderService.confirm_order() instead.
        This method is kept for backward compatibility but should not be used.
        """
        raise NotImplementedError("Use OrderService.confirm_order() instead")

    def commit_stock_reservations(self):
        """
        DEPRECATED: Use OrderService.complete_order() instead.
        This method is kept for backward compatibility but should not be used.
        """
        raise NotImplementedError("Use OrderService.complete_order() instead")

    def release_stock_reservations(self):
        """
        DEPRECATED: Use OrderService.cancel_order() instead.
        This method is kept for backward compatibility but should not be used.
        """
        raise NotImplementedError("Use OrderService.cancel_order() instead")

    # =========================
    # COMPLETE ORDER (CRITICAL)
    # =========================
    def complete_order(self):
        """
        DEPRECATED: Use OrderService.complete_order() instead.
        This method is kept for backward compatibility but should not be used.
        """
        raise NotImplementedError("Use OrderService.complete_order() instead")


class StockReservation(models.Model):
    order = models.ForeignKey(
        'Order', on_delete=models.CASCADE, related_name='stock_reservations'
    )
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name='stock_reservations'
    )
    reserved_quantity = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def release(self):
        """
        DEPRECATED: Use OrderService.cancel_order() or OrderService.complete_order() instead.
        This method is kept for backward compatibility but should not be used.
        """
        raise NotImplementedError("Use OrderService methods for reservation management")

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['active']),
            models.Index(fields=['expires_at']),
        ]


class OrderIdempotencyRecord(models.Model):
    key = models.CharField(max_length=255)
    endpoint = models.CharField(max_length=255)
    method = models.CharField(max_length=10)
    request_body = models.JSONField(null=True, blank=True)
    response_code = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('endpoint', 'key', 'method')
        indexes = [
            models.Index(fields=['endpoint', 'key', 'method']),
        ]


# =========================================================
# ORDER ITEMS
# =========================================================

class OrderItem(models.Model):

    STOCK_STATUS_CHOICES = [
        ('in_stock', 'In Stock'),
        ('low_stock', 'Low Stock'),
        ('out_of_stock', 'Out of Stock'),
    ]

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='items'
    )

    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL,
        null=True, related_name='order_items'
    )

    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='order_items'
    )

    quantity = models.PositiveIntegerField(default=1)

    # =========================
    # PRICING
    # =========================
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    override_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True
    )

    override_reason = models.CharField(max_length=255, blank=True)

    # 🔥 FINAL LOCKED PRICE
    final_unit_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True
    )

    customization_details = models.TextField(blank=True)

    customization_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00')
    )
    services = models.ManyToManyField(
        CustomizationService,
        blank=True,
        related_name='order_items'
    )

    stock_status_at_sale = models.CharField(
        max_length=20,
        choices=STOCK_STATUS_CHOICES,
        blank=True
    )

    # =========================
    # VALIDATION
    # =========================
    def clean(self):
        if self.order.transaction_type == 'quick_sale':
            if self.variant:
                available = self.variant.stock_quantity - self.variant.committed_quantity
                if self.quantity > available:
                    raise ValidationError(
                        f"Not enough stock for {self.product.name}. "
                        f"Available: {available}, Requested: {self.quantity}. "
                        f"Use Custom Order instead."
                    )

    # =========================
    # STOCK STATUS ENGINE
    # =========================
    def get_stock_status(self):
        if self.variant:
            available = self.variant.stock_quantity - self.variant.committed_quantity

            if available > 5:
                return 'in_stock'
            elif available > 0:
                return 'low_stock'
            else:
                return 'out_of_stock'

        return 'in_stock'

    # =========================
    # SAVE LOGIC (CORE ENGINE)
    # =========================
    def save(self, *args, **kwargs):
        # Lock final price on first save
        if not self.final_unit_price:
            self.final_unit_price = self.override_price or self.unit_price

        # Snapshot stock status at time of sale
        if not self.stock_status_at_sale:
            self.stock_status_at_sale = self.get_stock_status()

        super().save(*args, **kwargs)
        # NOTE: stock deduction and committed quantity changes
        # are handled entirely by signals in orders/signals.py
        # Do NOT put stock logic here to avoid double deductions.

    # =========================
    # CALCULATIONS
    # =========================
    @property
    def subtotal(self):
        return (self.final_unit_price + self.customization_price) * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


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
    
    

# =========================================================
# PAYMENTS
# =========================================================

class Payment(models.Model):

    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('mobile_money', 'Mobile Money'),
        ('bank_transfer', 'Bank Transfer'),
        ('adjustment', 'Adjustment'),
    ]

    PAYMENT_TYPE_CHOICES = [
        ('payment', 'Payment'),
        ('deposit', 'Deposit'),
        ('overpayment', 'Overpayment Credit'),
        ('refund', 'Refund'),
        ('reversal', 'Reversal'),
        ('writeoff', 'Write Off'),
    ]

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='payments'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash'
    )
    payment_type = models.CharField(
        max_length=20, choices=PAYMENT_TYPE_CHOICES, default='payment'
    )
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='processed_order_payments'
    )
    journal_entry = models.ForeignKey(
        'finance.JournalEntry', on_delete=models.PROTECT, null=True, blank=True, related_name='order_payments'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.order.recalculate_payment_status()

    def delete(self, *args, **kwargs):
        order = self.order
        super().delete(*args, **kwargs)
        order.recalculate_payment_status()

    def __str__(self):
        return f"Payment ${self.amount} on {self.order.order_number}"

    class Meta:
        ordering = ['-created_at']