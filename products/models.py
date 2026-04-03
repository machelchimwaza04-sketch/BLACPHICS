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

    # =========================
    # RELATION
    # =========================
    product = models.ForeignKey(
        'Product', on_delete=models.CASCADE, related_name='variants'
    )

    # =========================
    # ATTRIBUTES
    # =========================
    size = models.CharField(max_length=10, choices=SIZE_CHOICES)
    color = models.CharField(max_length=50)

    # Optional but 🔥 VERY IMPORTANT
    sku = models.CharField(max_length=50, unique=True, null=True, blank=True)

    # =========================
    # INVENTORY
    # =========================
    stock_quantity = models.PositiveIntegerField(default=0)

    # 🔥 NEW (CORE FEATURE)
    committed_quantity = models.PositiveIntegerField(default=0)

    # =========================
    # PRICING
    # =========================
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    extra_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # Optional override (else fallback to product selling price)
    selling_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True
    )

    # =========================
    # CONTROL
    # =========================
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # =========================
    # REPRESENTATION
    # =========================
    def __str__(self):
        return f"{self.product.name} - {self.size} - {self.color}"

    class Meta:
        unique_together = ('product', 'size', 'color')
        ordering = ['size', 'color']
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['product']),
        ]

    # =========================
    # CORE INVENTORY LOGIC
    # =========================
    @property
    def available_quantity(self):
        return self.stock_quantity - self.committed_quantity

    @property
    def is_in_stock(self):
        return self.available_quantity > 0

    # =========================
    # TRAFFIC LIGHT SYSTEM
    # =========================
    @property
    def stock_status(self):
        available = self.available_quantity

        if available <= 0:
            return 'out_of_stock'
        elif available <= getattr(self.product, 'low_stock_threshold', 5):
            return 'low_stock'
        return 'in_stock'

    # =========================
    # PRICING LOGIC
    # =========================
    @property
    def final_selling_price(self):
        """
        Variant price overrides product price if set
        """
        base_price = self.selling_price if self.selling_price else self.product.selling_price
        return base_price + self.extra_price

    # =========================
    # VALIDATION (VERY IMPORTANT)
    # =========================
    def clean(self):
        if self.committed_quantity > self.stock_quantity + self.committed_quantity:
            raise ValidationError("Invalid committed quantity.")

        if self.stock_quantity < 0:
            raise ValidationError("Stock cannot be negative.")

    # =========================
    # SAFE INVENTORY OPERATIONS
    # =========================
    def add_stock(self, quantity):
        if quantity < 0:
            raise ValidationError("Cannot add negative stock.")
        self.stock_quantity += quantity
        self.save()

    def reduce_stock(self, quantity):
        if quantity > self.stock_quantity:
            raise ValidationError("Not enough stock.")
        self.stock_quantity -= quantity
        self.save()

    def commit_stock(self, quantity):
        """
        Used for custom orders (reserve stock)
        """
        self.committed_quantity += quantity
        self.save()

    def release_committed_stock(self, quantity):
        """
        When order is cancelled or fulfilled
        """
        if quantity > self.committed_quantity:
            raise ValidationError("Cannot release more than committed.")
        self.committed_quantity -= quantity
        self.save()