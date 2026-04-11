from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.db import transaction
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
# HANDLE ORDER STATUS TRANSITIONS
# Only fires on STATUS CHANGES, not creation
# ==========================================
@receiver(post_save, sender=Order)
def handle_order_status_flow(sender, instance, **kwargs):
    previous = getattr(instance, '_previous_status', None)
    current = instance.status

    # No change — skip
    if previous == current:
        return

    with transaction.atomic():

        # Custom order confirmed → commit (reserve) stock
        if (instance.transaction_type == 'custom_order' and
                previous != 'confirmed' and current == 'confirmed'):
            for item in instance.items.all():
                if item.variant:
                    item.variant.committed_quantity += item.quantity
                    item.variant.save()

        # Custom order completed → deduct stock + release committed
        # Quick sale stock is handled on OrderItem creation below
        if (current == 'completed' and
                instance.transaction_type == 'custom_order'):
            for item in instance.items.all():
                if item.variant:
                    v = item.variant
                    v.stock_quantity = max(0, v.stock_quantity - item.quantity)
                    v.committed_quantity = max(0, v.committed_quantity - item.quantity)
                    v.save()

        # Order cancelled → release committed stock
        if current == 'cancelled':
            for item in instance.items.all():
                if item.variant and instance.transaction_type == 'custom_order':
                    item.variant.committed_quantity = max(
                        0, item.variant.committed_quantity - item.quantity
                    )
                    item.variant.save()


# ==========================================
# QUICK SALE STOCK DEDUCTION ON ITEM CREATION
# Quick sales are created with status=completed
# so the transition signal never fires for them.
# We deduct stock here when the OrderItem is saved.
# ==========================================
@receiver(post_save, sender=OrderItem)
def deduct_stock_for_quick_sale(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.order.transaction_type != 'quick_sale':
        return
    if not instance.variant:
        return
    with transaction.atomic():
        v = instance.variant
        v.stock_quantity = max(0, v.stock_quantity - instance.quantity)
        v.save()