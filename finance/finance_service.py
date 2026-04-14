"""
FinanceService: Encapsulates all finance business logic.
Handles:
- P&L calculations with Decimal precision
- Daily snapshots for historical reporting
- Revenue/expense categorization
"""

from datetime import date, timedelta
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Sum
from finance.models import DailyPLSnapshot, Expense, Revenue
from orders.models import Order, OrderItem
from suppliers.models import Purchase


class FinanceService:
    """
    Service layer for financial operations.
    All money math uses Decimal for bank-grade accuracy.
    """
    
    @staticmethod
    def calculate_pl_report(branch_id=None, period='month'):
        """
        Calculate P&L report using aggregation queries.
        Returns a dictionary with sales, cogs, expenses, and profit data.
        """
        from finance.services import calculate_pl_report as original_calc
        return original_calc(branch_id=branch_id, period=period)
    
    @staticmethod
    @transaction.atomic
    def create_daily_snapshot(branch_id, snapshot_date=None):
        """
        Create or update a daily P&L snapshot.
        Snapshots enable instant historical reporting without recalculation.
        """
        if snapshot_date is None:
            snapshot_date = date.today()
        
        # Check if snapshot already exists
        snapshot, created = DailyPLSnapshot.objects.get_or_create(
            branch_id=branch_id,
            snapshot_date=snapshot_date
        )
        
        # Calculate values
        start = snapshot_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
        order_filter = Q(status='completed', created_at__gte=start, created_at__lt=end)
        if branch_id:
            order_filter &= Q(branch_id=branch_id)
        
        orders = Order.objects.filter(order_filter)
        
        # Sales
        sales_revenue = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
        discount_total = orders.aggregate(Sum('discount_amount'))['discount_amount__sum'] or Decimal('0.00')
        net_sales = sales_revenue - discount_total
        total_collected = orders.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
        
        # COGS
        order_ids = orders.values_list('id', flat=True)
        items = OrderItem.objects.filter(order_id__in=order_ids)
        cogs = Decimal('0.00')
        for item in items:
            if item.variant and item.variant.cost_price:
                cogs += Decimal(str(item.variant.cost_price)) * Decimal(str(item.quantity))
        
        gross_profit = net_sales - cogs
        gross_margin = (gross_profit / net_sales * 100) if net_sales > 0 else Decimal('0.00')
        
        # Expenses
        exp_filter = Q(date__gte=snapshot_date, date__lt=snapshot_date + timedelta(days=1))
        if branch_id:
            exp_filter &= Q(branch_id=branch_id)
        
        manual_expenses = Expense.objects.filter(exp_filter).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        
        # Supplier payments
        pur_filter = Q(purchase_date__gte=snapshot_date, purchase_date__lt=snapshot_date + timedelta(days=1))
        if branch_id:
            pur_filter &= Q(branch_id=branch_id)
        
        supplier_payments = Purchase.objects.filter(pur_filter).aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
        
        # Manual revenue
        rev_filter = Q(date__gte=snapshot_date, date__lt=snapshot_date + timedelta(days=1))
        if branch_id:
            rev_filter &= Q(branch_id=branch_id)
        
        manual_revenue = Revenue.objects.filter(rev_filter).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        
        # Totals
        total_revenue = net_sales + manual_revenue
        total_expenses = manual_expenses + supplier_payments
        net_profit = total_revenue - cogs - total_expenses
        net_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else Decimal('0.00')
        
        # Update snapshot
        snapshot.sales_revenue = sales_revenue
        snapshot.discount_total = discount_total
        snapshot.net_sales = net_sales
        snapshot.total_collected = total_collected
        snapshot.cogs = cogs
        snapshot.gross_profit = gross_profit
        snapshot.gross_margin_pct = gross_margin
        snapshot.manual_expenses = manual_expenses
        snapshot.supplier_payments = supplier_payments
        snapshot.manual_revenue = manual_revenue
        snapshot.total_revenue = total_revenue
        snapshot.total_expenses = total_expenses
        snapshot.net_profit = net_profit
        snapshot.net_margin_pct = net_margin
        snapshot.order_count = orders.count()
        
        snapshot.save()
        
        return snapshot
