from django.conf import settings
from django.db import models
from branches.models import Branch
from products.models import Product


class Supplier(models.Model):
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    phone = models.CharField(max_length=20)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Purchase(models.Model):
    STATUS_CHOICES = [
        ('ordered', 'Ordered'),
        ('received', 'Received'),
        ('partially_received', 'Partially Received'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Fully Paid'),
    ]

    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='purchases'
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, related_name='purchases'
    )
    purchase_number = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='ordered')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True)
    purchase_date = models.DateField()
    expected_delivery = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Purchase {self.purchase_number} - {self.supplier}"

    @property
    def balance_due(self):
        return self.total_amount - self.amount_paid

    class Meta:
        ordering = ['-purchase_date']


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(
        Purchase, on_delete=models.CASCADE, related_name='items'
    )
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, related_name='purchase_items'
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    @property
    def subtotal(self):
        return self.unit_price * self.quantity


class PurchasePayment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
    ]

    PAYMENT_TYPE_CHOICES = [
        ('payment', 'Payment'),
        ('refund', 'Refund'),
        ('reversal', 'Reversal'),
    ]

    purchase = models.ForeignKey(
        Purchase, on_delete=models.CASCADE, related_name='payments'
    )
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='purchase_payments'
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
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='processed_purchase_payments'
    )
    journal_entry = models.ForeignKey(
        'finance.JournalEntry', on_delete=models.PROTECT, null=True, blank=True, related_name='purchase_payments'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['purchase', 'reference']),
        ]

    def __str__(self):
        return f"Supplier payment ${self.amount} for {self.purchase.purchase_number}"
