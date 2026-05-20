from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Q
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
from .models import ExpenseCategory, Expense, Revenue, Account, JournalEntry, AccountingPeriod
from .serializers import ExpenseCategorySerializer, ExpenseSerializer, RevenueSerializer
from .services import (
    calculate_pl_report, compile_trial_balance, compile_profit_loss, compile_balance_sheet,
    compile_cash_flow, compile_inventory_valuation,
    compile_accounts_receivable_aging, compile_accounts_payable_aging,
    close_accounting_period
)
from .reconciliation import ReconciliationService
from orders.models import Order, OrderItem
from suppliers.models import Purchase
from common.mixins import BranchScopedViewSetMixin
from common.selectors import FinanceSelector


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer


class ExpenseViewSet(BranchScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = FinanceSelector.get_expenses_for_period()
    serializer_class = ExpenseSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['description', 'category__name']

    def get_queryset(self):
        branch_param = self.request.query_params.get('branch')
        if self.request.user.is_admin and branch_param:
            queryset = FinanceSelector.get_expenses_for_period(branch_id=branch_param)
        else:
            queryset = FinanceSelector.get_expenses_for_period()
        return self.filter_queryset_by_branch(queryset)


class RevenueViewSet(BranchScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = FinanceSelector.get_revenue_for_period()
    serializer_class = RevenueSerializer

    def get_queryset(self):
        branch_param = self.request.query_params.get('branch')
        if self.request.user.is_admin and branch_param:
            queryset = FinanceSelector.get_revenue_for_period(branch_id=branch_param)
        else:
            queryset = FinanceSelector.get_revenue_for_period()
        return self.filter_queryset_by_branch(queryset)

    @action(detail=False, methods=['get'])
    def pl_report(self, request):
        branch_id = request.query_params.get('branch')
        period = request.query_params.get('period', 'month')
        report = calculate_pl_report(branch_id=branch_id, period=period)
        return Response(report)


# ============================
# GL-AUTHORITATIVE REPORTING
# ============================
class FinancialReportViewSet(viewsets.ViewSet):
    """
    GL-Authoritative Financial Reporting endpoints.
    All reports derive exclusively from the General Ledger.
    """
    permission_classes = [IsAuthenticated]

    def get_branch(self, request):
        if hasattr(request.user, 'profile') and hasattr(request.user.profile, 'branch'):
            return request.user.profile.branch
        return None

    @action(detail=False, methods=['get'])
    def trial_balance(self, request):
        """Trial Balance report showing all GL accounts and balances."""
        branch = self.get_branch(request)
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date', date.today().isoformat())

        try:
            start_date = date.fromisoformat(start_date) if start_date else None
            end_date = date.fromisoformat(end_date)
            report = compile_trial_balance(branch=branch, start_date=start_date, end_date=end_date)
            return Response(report, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def profit_loss(self, request):
        """Profit & Loss report for a period."""
        branch = self.get_branch(request)
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date', date.today().isoformat())

        try:
            start_date = date.fromisoformat(start_date) if start_date else None
            end_date = date.fromisoformat(end_date)
            report = compile_profit_loss(branch=branch, start_date=start_date, end_date=end_date)
            return Response(report, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def balance_sheet(self, request):
        """Balance Sheet showing assets, liabilities, and equity."""
        branch = self.get_branch(request)
        as_of_date = request.query_params.get('as_of_date', date.today().isoformat())

        try:
            as_of_date = date.fromisoformat(as_of_date)
            report = compile_balance_sheet(branch=branch, start_date=None, end_date=as_of_date)
            return Response(report, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def cash_flow(self, request):
        """Cash Flow statement showing operating, investing, and financing activities."""
        branch = self.get_branch(request)
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date', date.today().isoformat())

        try:
            start_date = date.fromisoformat(start_date) if start_date else None
            end_date = date.fromisoformat(end_date)
            report = compile_cash_flow(branch=branch, start_date=start_date, end_date=end_date)
            return Response(report, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def accounts_receivable_aging(self, request):
        """Accounts Receivable aging report derived from GL AR account (1100)."""
        branch = self.get_branch(request)
        as_of_date = request.query_params.get('as_of_date', date.today().isoformat())

        try:
            as_of_date = date.fromisoformat(as_of_date)
            report = compile_accounts_receivable_aging(branch=branch, as_of_date=as_of_date)
            return Response(report, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def accounts_payable_aging(self, request):
        """Accounts Payable aging report derived from GL AP account (2000)."""
        branch = self.get_branch(request)
        as_of_date = request.query_params.get('as_of_date', date.today().isoformat())

        try:
            as_of_date = date.fromisoformat(as_of_date)
            report = compile_accounts_payable_aging(branch=branch, as_of_date=as_of_date)
            return Response(report, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def inventory_valuation(self, request):
        """Inventory valuation report reconciling GL inventory asset to physical cost layers."""
        branch = self.get_branch(request)
        as_of_date = request.query_params.get('as_of_date', date.today().isoformat())

        try:
            as_of_date = date.fromisoformat(as_of_date)
            report = compile_inventory_valuation(branch=branch, as_of_date=as_of_date)
            return Response(report, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def reconciliation(self, request):
        """Run full reconciliation suite and return results."""
        branch = self.get_branch(request)
        as_of_date = request.data.get('as_of_date', date.today().isoformat())

        try:
            as_of_date = date.fromisoformat(as_of_date)
            results = ReconciliationService.run_full_reconciliation(
                branch=branch,
                as_of_date=as_of_date,
                persist=True
            )
            return Response(results, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


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
        branch_name = Branch.objects.get(id=branch_id).name
    except Branch.DoesNotExist:
        branch_name = 'All Branches'

    report = calculate_pl_report(branch_id=branch_id, period=period)

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