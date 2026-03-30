from django.db import models
from django.core.exceptions import ValidationError
from branches.models import Branch
from customers.models import Customer
from products.models import Product, ProductVariant


class Order(models.Model):
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
        ('partial', 'Partially Paid'),
        ('paid', 'Fully Paid'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('mobile_money', 'Mobile Money'),
        ('bank_transfer', 'Bank Transfer'),
    ]

    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='orders'
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, related_name='orders'
    )
    order_number = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True)
    notes = models.TextField(blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order {self.order_number} - {self.customer}"

    @property
    def balance_due(self):
        return self.total_amount - self.amount_paid

    class Meta:
        ordering = ['-created_at']


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='items'
    )
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, related_name='order_items'
    )
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items'
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    customization_details = models.TextField(blank=True)
    customization_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def clean(self):
        if self.variant:
            if self.quantity > self.variant.stock_quantity:
                raise ValidationError(
                    f"Not enough stock for {self.product.name} "
                    f"({self.variant.size} - {self.variant.color}). "
                    f"Available: {self.variant.stock_quantity}, "
                    f"Requested: {self.quantity}"
                )
        elif self.product:
            if self.quantity > self.product.stock_quantity:
                raise ValidationError(
                    f"Not enough stock for {self.product.name}. "
                    f"Available: {self.product.stock_quantity}, "
                    f"Requested: {self.quantity}"
                )

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    @property
    def subtotal(self):
        return (self.unit_price + self.customization_price) * self.quantity