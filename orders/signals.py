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
            for item in instance.items.select_related('variant').all():
                if item.variant:
                    variant = ProductVariant.objects.select_for_update().get(pk=item.variant.pk)
                    available = variant.stock_quantity - variant.committed_quantity
                    if item.quantity > available:
                        raise ValidationError(
                            f"Not enough stock to confirm custom order item {item.product.name}. "
                            f"Available: {available}, requested: {item.quantity}."
                        )
                    variant.committed_quantity += item.quantity
                    variant.save()

        # Custom order completed → deduct stock + release committed
        # Quick sale stock is handled on OrderItem creation below
        if (current == 'completed' and
                instance.transaction_type == 'custom_order'):
            for item in instance.items.select_related('variant').all():
                if item.variant:
                    variant = ProductVariant.objects.select_for_update().get(pk=item.variant.pk)
                    if item.quantity > variant.committed_quantity:
                        raise ValidationError(
                            f"Reserved quantity mismatch for custom order item {item.product.name}. "
                            f"Reserved: {variant.committed_quantity}, required: {item.quantity}."
                        )
                    if item.quantity > variant.stock_quantity:
                        raise ValidationError(
                            f"Not enough stock to complete custom order item {item.product.name}. "
                            f"Available: {variant.stock_quantity}, requested: {item.quantity}."
                        )
                    variant.stock_quantity = max(0, variant.stock_quantity - item.quantity)
                    variant.committed_quantity = max(0, variant.committed_quantity - item.quantity)
                    variant.save()

        # Order cancelled → release committed stock
        if current == 'cancelled':
            for item in instance.items.select_related('variant').all():
                if item.variant and instance.transaction_type == 'custom_order':
                    variant = ProductVariant.objects.select_for_update().get(pk=item.variant.pk)
                    variant.committed_quantity = max(0, variant.committed_quantity - item.quantity)
                    variant.save()


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
        variant = ProductVariant.objects.select_for_update().get(pk=instance.variant.pk)
        available = variant.stock_quantity - variant.committed_quantity
        if instance.quantity > available:
            raise ValidationError(
                f"Not enough stock for quick sale item {instance.product.name}. "
                f"Available: {available}, requested: {instance.quantity}."
            )
        variant.stock_quantity = max(0, variant.stock_quantity - instance.quantity)
        variant.save()