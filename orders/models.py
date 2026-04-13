from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

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

    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_reason = models.CharField(max_length=255, blank=True)

    # 🔥 Audit trail
    discount_approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='discount_approvals'
    )

    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # =========================
    # EXTRA
    # =========================
    notes = models.TextField(blank=True)
    estimated_completion = models.DateField(null=True, blank=True)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
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

    def recalculate_payment_status(self):
        total_paid = sum(
            float(p.amount) for p in self.payments.filter(payment_type='payment')
        ) - sum(
            float(p.amount) for p in self.payments.filter(payment_type='reversal')
        )
        self.amount_paid = total_paid
        discounted = float(self.discounted_total)
        if total_paid <= 0:
            self.payment_status = 'unpaid'
        elif total_paid < discounted:
            self.payment_status = 'partial'
        else:
            self.payment_status = 'paid'
        self.save(update_fields=['amount_paid', 'payment_status'])

    @classmethod
    def generate_order_number(cls, branch_id):
        """
        Generates a unique auto-incrementing order number per branch.
        Scans existing order numbers to find the highest used number
        and increments from there, guaranteeing no duplicates.
        """
        existing = cls.objects.filter(branch_id=branch_id)
        max_num = 0
        for order in existing:
            try:
                parts = order.order_number.split('-')
                num = int(parts[-1])
                if num > max_num:
                    max_num = num
            except (ValueError, IndexError):
                continue
        candidate = f"ORD-{str(max_num + 1).zfill(5)}"
        # Safety check — if somehow it still exists, keep incrementing
        while cls.objects.filter(order_number=candidate).exists():
            max_num += 1
            candidate = f"ORD-{str(max_num + 1).zfill(5)}"
        return candidate

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

    # =========================
    # COMPLETE ORDER (delegated — stock via signals / line items)
    # =========================
    def complete_order(self):
        from orders.services.order_service import OrderService
        OrderService.transition_to_completed(self)


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
        max_digits=10, decimal_places=2, default=0.00
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
    
    

# =========================================================
# PAYMENTS
# =========================================================

class Payment(models.Model):

    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('mobile_money', 'Mobile Money'),
        ('bank_transfer', 'Bank Transfer'),
    ]

    PAYMENT_TYPE_CHOICES = [
        ('payment', 'Payment'),
        ('overpayment', 'Overpayment Credit'),
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
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment ${self.amount} on {self.order.order_number}"

    class Meta:
        ordering = ['-created_at']