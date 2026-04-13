from django.db import transaction

from orders.models import Order


class OrderService:
    """
    Order lifecycle operations. Stock movements for completion are handled by
    orders.signals (status transitions and quick-sale line items) — this
    service only performs safe, idempotent status updates.
    """

    @staticmethod
    @transaction.atomic
    def transition_to_completed(order: Order) -> Order:
        locked = Order.objects.select_for_update().get(pk=order.pk)
        if locked.status == 'completed':
            return locked
        locked.status = 'completed'
        locked.update_payment_status()
        locked.save(update_fields=['status', 'payment_status'])
        return locked
