from django.contrib import admin
from .models import Category, Product, ProductVariant, CustomizationService


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


from django.contrib import admin
from .models import ProductVariant


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):

    list_display = (
        'product',
        'size',
        'color',
        'sku',
        'stock_quantity',
        'committed_quantity',
        'available_quantity',
        'stock_status',
        'final_selling_price',
        'is_active',
    )

    list_filter = (
        'size',
        'color',
        'is_active',
        'product',
    )

    search_fields = (
        'product__name',
        'sku',
        'color',
    )

    list_editable = (
        'stock_quantity',
        'is_active',
    )

    readonly_fields = (
        'available_quantity',
        'stock_status',
        'created_at',
        'updated_at',
    )
@admin.register(CustomizationService)
class CustomizationServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'is_active', 'created_at']
    list_editable = ['is_active']
    search_fields = ['name', 'description']