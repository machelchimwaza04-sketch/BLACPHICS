from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Order


# ==========================================
# TRACK PREVIOUS STATUS (CRITICAL)
# ==========================================
@receiver(pre_save, sender=Order)
def track_previous_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            previous = Order.objects.get(pk=instance.pk)
            instance._previous_status = previous.status
        except Order.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


# ==========================================
# MAIN ORDER AUTOMATION ENGINE
# ==========================================
@receiver(post_save, sender=Order)
def handle_order_status_flow(sender, instance, created, **kwargs):

    previous_status = getattr(instance, '_previous_status', None)
    current_status = instance.status

    # ==============================
    # 1. CUSTOM ORDER CONFIRMATION
    # ==============================
    if (
        instance.transaction_type == 'custom_order'
        and current_status == 'confirmed'
        and previous_status != 'confirmed'
    ):
        for item in instance.items.all():
            if item.variant:
                item.variant.committed_quantity += item.quantity
                item.variant.save()

    # ==============================
    # 2. ORDER COMPLETION
    # ==============================
    if current_status == 'completed' and previous_status != 'completed':

        for item in instance.items.all():

            if item.variant:
                variant = item.variant

                # Deduct stock
                if variant.stock_quantity >= item.quantity:
                    variant.stock_quantity -= item.quantity

                # Release committed stock (for custom orders)
                if instance.transaction_type == 'custom_order':
                    variant.committed_quantity = max(
                        0, variant.committed_quantity - item.quantity
                    )

                variant.save()

            elif item.product:
                product = item.product

                if product.stock_quantity >= item.quantity:
                    product.stock_quantity -= item.quantity

                product.save()

    # ==============================
    # 3. ORDER CANCELLATION
    # ==============================
    if current_status == 'cancelled' and previous_status != 'cancelled':

        for item in instance.items.all():
            if item.variant:
                variant = item.variant

                # Release committed stock safely
                if variant.committed_quantity >= item.quantity:
                    variant.committed_quantity -= item.quantity

                variant.save()