from django.contrib import admin
from .models import Supplier, Purchase, PurchaseItem


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_person', 'phone', 'email', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'contact_person', 'email', 'phone']
    list_editable = ['is_active']


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ['purchase_number', 'branch', 'supplier', 'status', 'payment_status', 'total_amount', 'amount_paid', 'balance_due', 'purchase_date']
    list_filter = ['branch', 'status', 'payment_status', 'supplier']
    search_fields = ['purchase_number', 'supplier__name']
    list_editable = ['status', 'payment_status']
    inlines = [PurchaseItemInline]
    ordering = ['-purchase_date']


@admin.register(PurchaseItem)
class PurchaseItemAdmin(admin.ModelAdmin):
    list_display = ['purchase', 'product', 'quantity', 'unit_price', 'subtotal']
    search_fields = ['purchase__purchase_number', 'product__name']