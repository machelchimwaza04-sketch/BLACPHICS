from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Sum, Q
from django.utils import timezone

from branches.models import Branch
from finance.models import DailyPLSnapshot, Expense, Revenue
from orders.models import Order, OrderItem
from suppliers.models import Purchase


def _period_start(period: str, today: date) -> date | None:
    if period == 'month':
        return today.replace(day=1)
    if period == 'quarter':
        month = ((today.month - 1) // 3) * 3 + 1
        return today.replace(month=month, day=1)
    if period == 'year':
        return today.replace(month=1, day=1)
    return None


def calculate_daily_snapshot(branch: Branch, day: date) -> DailyPLSnapshot:
    """
    Aggregate one branch-day for snapshot storage (optional nightly job).
    """
    start = timezone.make_aware(datetime.combine(day, time.min))
    end = start + timedelta(days=1)

    order_filter = Q(branch=branch, status='completed', created_at__gte=start, created_at__lt=end)
    orders = Order.objects.filter(order_filter)
    net_sales = Decimal('0')
    for o in orders:
        net_sales += o.total_amount - o.discount_amount

    cogs = Decimal('0')
    order_ids = orders.values_list('id', flat=True)
    for item in OrderItem.objects.filter(order_id__in=order_ids).select_related('variant'):
        if item.variant and item.variant.cost_price:
            cogs += item.variant.cost_price * item.quantity

    manual_expenses = Expense.objects.filter(branch=branch, date=day).aggregate(
        t=Sum('amount')
    )['t'] or Decimal('0')

    manual_revenue = Revenue.objects.filter(branch=branch, date=day).aggregate(
        t=Sum('amount')
    )['t'] or Decimal('0')

    pur = Purchase.objects.filter(branch=branch, purchase_date=day)
    supplier_payments = pur.aggregate(t=Sum('amount_paid'))['t'] or Decimal('0')

    total_revenue = net_sales + manual_revenue
    total_expenses = manual_expenses + supplier_payments
    net_profit = total_revenue - cogs - total_expenses

    snap, _ = DailyPLSnapshot.objects.update_or_create(
        branch=branch,
        date=day,
        defaults={
            'total_revenue': total_revenue,
            'total_expenses': total_expenses,
            'cogs': cogs,
            'net_profit': net_profit,
        },
    )
    return snap


def get_snapshot_rollup(branch_id: int | None, start: date | None, end: date) -> dict | None:
    """
    If snapshots exist for the window, return rolled-up decimals; else None.
    """
    if not branch_id or not start:
        return None
    qs = DailyPLSnapshot.objects.filter(branch_id=branch_id, date__gte=start, date__lte=end)
    if not qs.exists():
        return None
    agg = qs.aggregate(
        total_revenue=Sum('total_revenue'),
        total_expenses=Sum('total_expenses'),
        cogs=Sum('cogs'),
        net_profit=Sum('net_profit'),
    )
    return {k: (v or Decimal('0')) for k, v in agg.items()}
