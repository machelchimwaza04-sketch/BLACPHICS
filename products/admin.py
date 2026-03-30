from django.contrib import admin
from .models import Category, Product, ProductVariant


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'branch', 'category', 'item_type', 'base_price', 'stock_quantity', 'is_low_stock', 'is_active']
    list_filter = ['branch', 'category', 'item_type', 'is_active']
    search_fields = ['name', 'description']
    list_editable = ['is_active']
    inlines = [ProductVariantInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['product', 'size', 'color', 'stock_quantity', 'extra_price', 'is_available']
    list_filter = ['size', 'color', 'is_available']
    search_fields = ['product__name', 'color']
    list_editable = ['is_available']