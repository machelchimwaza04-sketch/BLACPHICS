from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'branch', 'customer', 'status', 'payment_status', 'total_amount', 'amount_paid', 'balance_due', 'created_at']
    list_filter = ['branch', 'status', 'payment_status', 'payment_method']
    search_fields = ['order_number', 'customer__first_name', 'customer__last_name']
    list_editable = ['status', 'payment_status']
    inlines = [OrderItemInline]
    ordering = ['-created_at']


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'variant', 'quantity', 'unit_price', 'customization_details', 'subtotal']
    search_fields = ['order__order_number', 'product__name']
    list_filter = ['product']