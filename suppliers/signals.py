from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from .models import Purchase
from .services.purchase_service import PurchaseService


@receiver(pre_save, sender=Purchase)
def track_purchase_previous_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_purchase_status = None
        return
    try:
        instance._previous_purchase_status = Purchase.objects.get(pk=instance.pk).status
    except Purchase.DoesNotExist:
        instance._previous_purchase_status = None


@receiver(post_save, sender=Purchase)
def apply_inventory_on_received(sender, instance, **kwargs):
    prev = getattr(instance, '_previous_purchase_status', None)
    if instance.status == 'received' and prev != 'received':
        PurchaseService.apply_received_inventory(instance)
