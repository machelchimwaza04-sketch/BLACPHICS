from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta, date
from .models import ExpenseCategory, Expense, Revenue
from .serializers import ExpenseCategorySerializer, ExpenseSerializer, RevenueSerializer
from orders.models import Order, OrderItem
from suppliers.models import Purchase


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['description', 'category__name']

    def get_queryset(self):
        qs = Expense.objects.all()
        branch = self.request.query_params.get('branch')
        if branch:
            qs = qs.filter(branch=branch)
        return qs


class RevenueViewSet(viewsets.ModelViewSet):
    queryset = Revenue.objects.all()
    serializer_class = RevenueSerializer

    def get_queryset(self):
        qs = Revenue.objects.all()
        branch = self.request.query_params.get('branch')
        if branch:
            qs = qs.filter(branch=branch)
        return qs

    @action(detail=False, methods=['get'])
    def pl_report(self, request):
        branch_id = request.query_params.get('branch')
        period = request.query_params.get('period', 'month')  # month, quarter, year, all

        # Date range
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

        # =====================
        # SALES REVENUE
        # =====================
        orders = Order.objects.filter(order_filter)
        sales_revenue = float(
            orders.aggregate(t=Sum('total_amount'))['t'] or 0
        )
        discount_total = float(
            orders.aggregate(t=Sum('discount_amount'))['t'] or 0
        )
        net_sales = sales_revenue - discount_total
        total_collected = float(
            orders.aggregate(t=Sum('amount_paid'))['t'] or 0
        )
        accounts_receivable = net_sales - total_collected

        # =====================
        # COGS
        # =====================
        order_ids = orders.values_list('id', flat=True)
        items = OrderItem.objects.filter(order_id__in=order_ids)
        cogs = 0
        for item in items:
            if item.variant and item.variant.cost_price:
                cogs += float(item.variant.cost_price) * item.quantity
        gross_profit = net_sales - cogs
        gross_margin_pct = round((gross_profit / net_sales * 100), 2) if net_sales > 0 else 0

        # =====================
        # MANUAL EXPENSES
        # =====================
        exp_filter = Q()
        if branch_id:
            exp_filter &= Q(branch_id=branch_id)
        if start:
            exp_filter &= Q(date__gte=start)
        manual_expenses = float(
            Expense.objects.filter(exp_filter).aggregate(t=Sum('amount'))['t'] or 0
        )

        # Expenses by category
        expense_by_category = list(
            Expense.objects.filter(exp_filter)
            .values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )

        # =====================
        # SUPPLIER PAYMENTS (AP)
        # =====================
        pur_filter = Q()
        if branch_id:
            pur_filter &= Q(branch_id=branch_id)
        if start:
            pur_filter &= Q(purchase_date__gte=start)
        supplier_payments = float(
            Purchase.objects.filter(pur_filter)
            .aggregate(t=Sum('amount_paid'))['t'] or 0
        )
        supplier_outstanding = float(
            Purchase.objects.filter(pur_filter)
            .aggregate(t=Sum('total_amount'))['t'] or 0
        ) - supplier_payments

        # =====================
        # MANUAL REVENUE
        # =====================
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

        # =====================
        # MONTHLY TREND (last 6 months)
        # =====================
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

        return Response({
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
        })
    
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny

@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def export_pl_report(request):
    from .exports import generate_pl_pdf, generate_pl_excel
    branch_id = request.query_params.get('branch')
    period = request.query_params.get('period', 'month')
    fmt = request.query_params.get('format', 'pdf')

    from branches.models import Branch
    try:
        branch = Branch.objects.get(id=branch_id)
        branch_name = branch.name
    except:
        branch_name = 'All Branches'

    # Build report data
    from django.db.models import Sum, Q
    from datetime import date, timedelta
    from orders.models import Order, OrderItem
    from suppliers.models import Purchase
    from .models import Expense, Revenue

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

    order_ids = orders.values_list('id', flat=True)
    items = OrderItem.objects.filter(order_id__in=order_ids)
    cogs = sum(float(i.variant.cost_price) * i.quantity for i in items if i.variant and i.variant.cost_price)
    gross_profit = net_sales - cogs
    gross_margin_pct = round((gross_profit / net_sales * 100), 2) if net_sales > 0 else 0

    exp_filter = Q()
    if branch_id: exp_filter &= Q(branch_id=branch_id)
    if start: exp_filter &= Q(date__gte=start)
    manual_expenses = float(Expense.objects.filter(exp_filter).aggregate(t=Sum('amount'))['t'] or 0)

    pur_filter = Q()
    if branch_id: pur_filter &= Q(branch_id=branch_id)
    if start: pur_filter &= Q(purchase_date__gte=start)
    supplier_payments = float(Purchase.objects.filter(pur_filter).aggregate(t=Sum('amount_paid'))['t'] or 0)
    supplier_outstanding = float(Purchase.objects.filter(pur_filter).aggregate(t=Sum('total_amount'))['t'] or 0) - supplier_payments

    rev_filter = Q()
    if branch_id: rev_filter &= Q(branch_id=branch_id)
    if start: rev_filter &= Q(date__gte=start)
    manual_revenue = float(Revenue.objects.filter(rev_filter).aggregate(t=Sum('amount'))['t'] or 0)

    total_revenue = net_sales + manual_revenue
    total_expenses = manual_expenses + supplier_payments
    net_profit = total_revenue - cogs - total_expenses
    net_margin_pct = round((net_profit / total_revenue * 100), 2) if total_revenue > 0 else 0

    trend = []
    for i in range(5, -1, -1):
        m_start = (today.replace(day=1) - timedelta(days=i*30)).replace(day=1)
        m_end = m_start.replace(month=m_start.month % 12 + 1, day=1) if m_start.month < 12 else m_start.replace(year=m_start.year+1, month=1, day=1)
        mf = Q(status='completed', created_at__date__gte=m_start, created_at__date__lt=m_end)
        if branch_id: mf &= Q(branch_id=branch_id)
        m_rev = float(Order.objects.filter(mf).aggregate(t=Sum('total_amount'))['t'] or 0)
        mef = Q(date__gte=m_start, date__lt=m_end)
        if branch_id: mef &= Q(branch_id=branch_id)
        m_exp = float(Expense.objects.filter(mef).aggregate(t=Sum('amount'))['t'] or 0)
        trend.append({'month': m_start.strftime('%b %Y'), 'revenue': m_rev, 'expenses': m_exp, 'profit': m_rev - m_exp})

    report = {
        'sales': {
            'gross_sales': sales_revenue, 'discounts': discount_total,
            'net_sales': net_sales, 'total_collected': total_collected,
            'accounts_receivable': net_sales - total_collected,
            'manual_revenue': manual_revenue, 'total_revenue': total_revenue,
        },
        'cogs': cogs, 'gross_profit': gross_profit, 'gross_margin_pct': gross_margin_pct,
        'expenses': {
            'manual': manual_expenses, 'supplier_payments': supplier_payments,
            'supplier_outstanding': supplier_outstanding, 'total': total_expenses,
        },
        'net_profit': net_profit, 'net_margin_pct': net_margin_pct, 'trend': trend,
    }

    if fmt == 'excel':
        buffer = generate_pl_excel(report, branch_name, period)
        response = HttpResponse(buffer.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="pl_report_{period}.xlsx"'
    else:
        buffer = generate_pl_pdf(report, branch_name, period)
        response = HttpResponse(buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="pl_report_{period}.pdf"'

    return response


@api_view(['GET'])
def export_orders_report(request):
    from .exports import generate_orders_pdf, generate_orders_excel
    from orders.models import Order
    from orders.serializers import OrderSerializer
    from branches.models import Branch

    branch_id = request.query_params.get('branch')
    fmt = request.query_params.get('format', 'pdf')

    try:
        branch_name = Branch.objects.get(id=branch_id).name
    except:
        branch_name = 'All Branches'

    orders_qs = Order.objects.all()
    if branch_id:
        orders_qs = orders_qs.filter(branch_id=branch_id)
    orders_data = OrderSerializer(orders_qs, many=True).data

    if fmt == 'excel':
        buffer = generate_orders_excel(orders_data, branch_name)
        response = HttpResponse(buffer.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="orders_report.xlsx"'
    else:
        buffer = generate_orders_pdf(orders_data, branch_name)
        response = HttpResponse(buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="orders_report.pdf"'

    return response