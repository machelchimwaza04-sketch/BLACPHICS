from django.db import models
from branches.models import Branch
from django.db import models
from django.core.exceptions import ValidationError

class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"


class Product(models.Model):
    ITEM_TYPE_CHOICES = [
        ('plain', 'Plain'),
        ('customizable', 'Customizable'),
    ]

    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='products'
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, related_name='products'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES, default='plain')
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    customization_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.branch.name})"

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold

    @property
    def total_price(self):
        return self.base_price + self.customization_price

    class Meta:
        ordering = ['name']

class ProductVariant(models.Model):
    SIZE_CHOICES = [
        ('XS', 'Extra Small'),
        ('S', 'Small'),
        ('M', 'Medium'),
        ('L', 'Large'),
        ('XL', 'Extra Large'),
        ('XXL', 'Double Extra Large'),
        ('XXXL', 'Triple Extra Large'),
    ]

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='variants'
    )
    size = models.CharField(max_length=10, choices=SIZE_CHOICES)
    color = models.CharField(max_length=50)
    stock_quantity = models.PositiveIntegerField(default=0)
    committed_quantity = models.PositiveIntegerField(default=0)
    cost_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text='Purchase cost price for COGS calculation'
    )
    extra_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.product.name} - {self.size} - {self.color}"

    @property
    def available_quantity(self):
        return self.stock_quantity - self.committed_quantity

    @property
    def stock_status(self):
        if self.available_quantity <= 0:
            return 'out_of_stock'
        elif self.available_quantity <= self.product.low_stock_threshold:
            return 'low_stock'
        return 'in_stock'

    @property
    def selling_price(self):
        return float(self.product.base_price) + float(self.extra_price)

    @property
    def gross_margin(self):
        sp = self.selling_price
        cp = float(self.cost_price)
        if cp > 0 and sp > 0:
            return round(((sp - cp) / sp) * 100, 2)
        return None

    def add_stock(self, quantity):
        self.stock_quantity += quantity
        self.save()

    def reduce_stock(self, quantity):
        if quantity > self.stock_quantity:
            raise ValueError("Not enough stock.")
        self.stock_quantity -= quantity
        self.save()

    def commit_stock(self, quantity):
        self.committed_quantity += quantity
        self.save()

    def release_committed_stock(self, quantity):
        if quantity > self.committed_quantity:
            raise ValueError("Cannot release more than committed.")
        self.committed_quantity -= quantity
        self.save()

    class Meta:
        unique_together = ('product', 'size', 'color')
        ordering = ['size', 'color']

class CustomizationService(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} (${self.price})"

    class Meta:
        ordering = ['name']  