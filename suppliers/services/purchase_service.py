from django.db import transaction

from suppliers.models import Purchase


class PurchaseService:
    """Purchase payments and inventory receipt (idempotent receive)."""

    @staticmethod
    @transaction.atomic
    def record_payment(purchase: Purchase, amount) -> Purchase:
        from decimal import Decimal

        amt = Decimal(str(amount))
        if amt <= 0:
            raise ValueError('Invalid amount')
        p = Purchase.objects.select_for_update().get(pk=purchase.pk)
        new_paid = p.amount_paid + amt
        if new_paid >= p.total_amount:
            p.amount_paid = p.total_amount
            p.payment_status = 'paid'
        else:
            p.amount_paid = new_paid
            p.payment_status = 'partial'
        p.save(update_fields=['amount_paid', 'payment_status'])
        return p

    @staticmethod
    @transaction.atomic
    def apply_received_inventory(purchase: Purchase) -> None:
        """
        Increase on-hand stock for each line when a purchase is received.
        Called once per transition into 'received'.
        """
        p = Purchase.objects.select_for_update().get(pk=purchase.pk)
        for item in p.items.select_related('product').all():
            if item.product:
                item.product.stock_quantity += item.quantity
                item.product.save(update_fields=['stock_quantity'])
