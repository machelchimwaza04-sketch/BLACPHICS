from datetime import date, timedelta

from django.db.models import Q, Sum

from finance.models import Expense, Revenue
from orders.models import Order, OrderItem
from suppliers.models import Purchase


def get_pl_report_payload(branch_id: str | None, period: str = 'month') -> dict:
    """
    Builds the P&L JSON structure used by the API and export views.
    """
    today = date.today()
    if period == 'month':
        start = today.replace(day=1)
    elif period == 'quarter':
        month = ((today.month - 1) // 3) * 3 + 1
        start = today.replace(month=month, day=1)
    elif period == 'year':
        start = today.replace(month=1, day=1)
    else:
        start = None

    order_filter = Q(status='completed')
    if branch_id:
        order_filter &= Q(branch_id=branch_id)
    if start:
        order_filter &= Q(created_at__date__gte=start)

    orders = Order.objects.filter(order_filter)
    sales_revenue = float(orders.aggregate(t=Sum('total_amount'))['t'] or 0)
    discount_total = float(orders.aggregate(t=Sum('discount_amount'))['t'] or 0)
    net_sales = sales_revenue - discount_total
    total_collected = float(orders.aggregate(t=Sum('amount_paid'))['t'] or 0)
    accounts_receivable = net_sales - total_collected

    order_ids = orders.values_list('id', flat=True)
    items = OrderItem.objects.filter(order_id__in=order_ids)
    cogs = 0.0
    for item in items:
        if item.variant and item.variant.cost_price:
            cogs += float(item.variant.cost_price) * item.quantity
    gross_profit = net_sales - cogs
    gross_margin_pct = round((gross_profit / net_sales * 100), 2) if net_sales > 0 else 0

    exp_filter = Q()
    if branch_id:
        exp_filter &= Q(branch_id=branch_id)
    if start:
        exp_filter &= Q(date__gte=start)
    manual_expenses = float(
        Expense.objects.filter(exp_filter).aggregate(t=Sum('amount'))['t'] or 0
    )

    expense_by_category = list(
        Expense.objects.filter(exp_filter)
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )

    pur_filter = Q()
    if branch_id:
        pur_filter &= Q(branch_id=branch_id)
    if start:
        pur_filter &= Q(purchase_date__gte=start)
    supplier_payments = float(
        Purchase.objects.filter(pur_filter).aggregate(t=Sum('amount_paid'))['t'] or 0
    )
    supplier_outstanding = float(
        Purchase.objects.filter(pur_filter).aggregate(t=Sum('total_amount'))['t'] or 0
    ) - supplier_payments

    rev_filter = Q()
    if branch_id:
        rev_filter &= Q(branch_id=branch_id)
    if start:
        rev_filter &= Q(date__gte=start)
    manual_revenue = float(
        Revenue.objects.filter(rev_filter).aggregate(t=Sum('amount'))['t'] or 0
    )

    total_revenue = net_sales + manual_revenue
    total_expenses = manual_expenses + supplier_payments
    operating_profit = gross_profit - manual_expenses
    net_profit = total_revenue - cogs - total_expenses
    net_margin_pct = round((net_profit / total_revenue * 100), 2) if total_revenue > 0 else 0

    trend = []
    for i in range(5, -1, -1):
        m_start = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        if m_start.month == 12:
            m_end = m_start.replace(year=m_start.year + 1, month=1, day=1)
        else:
            m_end = m_start.replace(month=m_start.month + 1, day=1)

        m_filter = Q(status='completed', created_at__date__gte=m_start, created_at__date__lt=m_end)
        if branch_id:
            m_filter &= Q(branch_id=branch_id)
        m_orders = Order.objects.filter(m_filter)
        m_revenue = float(m_orders.aggregate(t=Sum('total_amount'))['t'] or 0)

        m_exp_filter = Q(date__gte=m_start, date__lt=m_end)
        if branch_id:
            m_exp_filter &= Q(branch_id=branch_id)
        m_expenses = float(Expense.objects.filter(m_exp_filter).aggregate(t=Sum('amount'))['t'] or 0)

        trend.append({
            'month': m_start.strftime('%b %Y'),
            'revenue': m_revenue,
            'expenses': m_expenses,
            'profit': m_revenue - m_expenses,
        })

    return {
        'period': period,
        'start_date': str(start) if start else 'all time',
        'sales': {
            'gross_sales': round(sales_revenue, 2),
            'discounts': round(discount_total, 2),
            'net_sales': round(net_sales, 2),
            'total_collected': round(total_collected, 2),
            'accounts_receivable': round(accounts_receivable, 2),
            'manual_revenue': round(manual_revenue, 2),
            'total_revenue': round(total_revenue, 2),
            'order_count': orders.count(),
        },
        'cogs': round(cogs, 2),
        'gross_profit': round(gross_profit, 2),
        'gross_margin_pct': gross_margin_pct,
        'expenses': {
            'manual': round(manual_expenses, 2),
            'supplier_payments': round(supplier_payments, 2),
            'supplier_outstanding': round(supplier_outstanding, 2),
            'total': round(total_expenses, 2),
            'by_category': expense_by_category,
        },
        'operating_profit': round(operating_profit, 2),
        'net_profit': round(net_profit, 2),
        'net_margin_pct': net_margin_pct,
        'trend': trend,
    }
