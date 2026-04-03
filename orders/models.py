from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

from branches.models import Branch
from customers.models import Customer
from products.models import Product, ProductVariant


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
    # COMPLETE ORDER (CRITICAL)
    # =========================
    def complete_order(self):
        if self.status == 'completed':
            return

        for item in self.items.all():
            if item.variant:
                if self.is_quick_sale:
                    item.variant.stock_quantity -= item.quantity
                else:
                    # custom order fulfillment
                    item.variant.committed_quantity -= item.quantity
                    item.variant.stock_quantity -= item.quantity

                item.variant.save()

        self.status = 'completed'
        self.update_payment_status()
        self.save()


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
        is_new = self.pk is None

        # Lock final price
        if not self.final_unit_price:
            self.final_unit_price = self.override_price or self.unit_price

        # Set stock status snapshot
        if not self.stock_status_at_sale:
            self.stock_status_at_sale = self.get_stock_status()

        super().save(*args, **kwargs)

        # 🔥 Commit stock for custom orders
        if is_new and self.order.is_custom_order:
            if self.variant:
                self.variant.committed_quantity += self.quantity
                self.variant.save()

    # =========================
    # CALCULATIONS
    # =========================
    @property
    def subtotal(self):
        return (self.final_unit_price + self.customization_price) * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"