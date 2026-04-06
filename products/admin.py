from django.contrib import admin
from .models import Category, Product, ProductVariant, CustomizationService


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ['size', 'color', 'stock_quantity', 'committed_quantity',
              'cost_price', 'extra_price', 'is_available']
    readonly_fields = ['available_quantity', 'stock_status']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'branch', 'category', 'item_type',
                    'base_price', 'stock_quantity', 'is_low_stock', 'is_active']
    list_filter = ['branch', 'category', 'item_type', 'is_active']
    search_fields = ['name', 'description']
    list_editable = ['is_active']
    inlines = [ProductVariantInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['product', 'size', 'color', 'stock_quantity',
                    'committed_quantity', 'available_quantity',
                    'cost_price', 'extra_price', 'stock_status', 'is_available']
    list_filter = ['size', 'color', 'is_available', 'product']
    search_fields = ['product__name', 'color']
    list_editable = ['stock_quantity', 'is_available']
    readonly_fields = ['available_quantity', 'stock_status',
                       'selling_price', 'gross_margin']


@admin.register(CustomizationService)
class CustomizationServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'is_active']
    list_editable = ['is_active']
    search_fields = ['name', 'description']