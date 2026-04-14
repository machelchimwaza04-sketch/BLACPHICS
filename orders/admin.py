from django.contrib import admin
from .models import Order, OrderItem, Payment


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ['created_at']
    fields = ['amount', 'method', 'payment_type', 'reference', 'notes', 'created_at']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'branch', 'customer', 'status', 'payment_status', 'total_amount', 'amount_paid', 'balance_due', 'created_at']
    list_filter = ['branch', 'status', 'payment_status', 'payment_method']
    search_fields = ['order_number', 'customer__first_name', 'customer__last_name']
    list_editable = ['status', 'payment_status']
    inlines = [OrderItemInline, PaymentInline]
    ordering = ['-created_at']


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'variant', 'quantity', 'unit_price', 'customization_details', 'subtotal']
    search_fields = ['order__order_number', 'product__name']
    list_filter = ['product']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['order', 'amount', 'method', 'payment_type', 'reference', 'created_at']
    list_filter = ['method', 'payment_type']
    search_fields = ['order__order_number', 'reference', 'notes']
    ordering = ['-created_at']