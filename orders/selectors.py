from django.db.models import Prefetch

from orders.models import Order, OrderItem, Payment


def orders_for_branch(branch_id, status=None):
    qs = (
        Order.objects.filter(branch_id=branch_id)
        .select_related('branch', 'customer', 'created_by', 'discount_approved_by')
        .order_by('-created_at')
    )
    if status:
        qs = qs.filter(status=status)
    return qs


def order_detail_selector(order_id):
    return (
        Order.objects.filter(pk=order_id)
        .select_related('branch', 'customer')
        .prefetch_related(
            Prefetch('items', queryset=OrderItem.objects.select_related('product', 'variant')),
            Prefetch('payments', queryset=Payment.objects.all()),
        )
        .first()
    )
