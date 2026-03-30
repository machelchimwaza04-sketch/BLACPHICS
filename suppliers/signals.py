from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Purchase


@receiver(post_save, sender=Purchase)
def increase_stock_on_delivery(sender, instance, **kwargs):
    if instance.status == 'received':
        for item in instance.items.all():
            if item.product:
                item.product.stock_quantity += item.quantity
                item.product.save()