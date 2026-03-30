from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order


@receiver(post_save, sender=Order)
def deduct_stock_on_completion(sender, instance, **kwargs):
    if instance.status == 'completed':
        for item in instance.items.all():
            if item.variant:
                if item.variant.stock_quantity >= item.quantity:
                    item.variant.stock_quantity -= item.quantity
                    item.variant.save()
            elif item.product:
                if item.product.stock_quantity >= item.quantity:
                    item.product.stock_quantity -= item.quantity
                    item.product.save()