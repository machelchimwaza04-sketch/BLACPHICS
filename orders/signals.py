from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.db import transaction
from products.models import ProductVariant
from .models import Order, OrderItem


# ==========================================
# TRACK PREVIOUS STATUS BEFORE SAVE
# ==========================================
@receiver(pre_save, sender=Order)
def track_previous_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    try:
        instance._previous_status = Order.objects.get(pk=instance.pk).status
    except Order.DoesNotExist:
        instance._previous_status = None


# ==========================================
# DEPRECATED: SIGNAL-DRIVEN STOCK MUTATION REMOVED
# All stock operations now handled by OrderService and InventoryService
# ==========================================
# @receiver(post_save, sender=Order)
# def handle_order_status_flow(sender, instance, **kwargs):
#     # REMOVED: Stock mutation logic moved to OrderService


# ==========================================
# DEPRECATED: SIGNAL-DRIVEN STOCK MUTATION REMOVED
# Quick sale stock deduction now handled by OrderService.complete_order()
# ==========================================
# @receiver(post_save, sender=OrderItem)
# def deduct_stock_for_quick_sale(sender, instance, created, **kwargs):
#     # REMOVED: Stock mutation logic moved to OrderService