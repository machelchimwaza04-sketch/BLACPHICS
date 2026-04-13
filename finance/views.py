from django.http import HttpResponse
from rest_framework import viewsets, filters
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from common.branch_scope import BranchScopedQuerysetMixin
from branches.models import Branch
from .models import ExpenseCategory, Expense, Revenue
from .serializers import ExpenseCategorySerializer, ExpenseSerializer, RevenueSerializer
from .selectors import get_pl_report_payload


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer


class ExpenseViewSet(BranchScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'description', 'category__name']


class RevenueViewSet(BranchScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Revenue.objects.all()
    serializer_class = RevenueSerializer

    @action(detail=False, methods=['get'])
    def pl_report(self, request):
        branch_id = request.query_params.get('branch')
        period = request.query_params.get('period', 'month')
        return Response(get_pl_report_payload(branch_id, period))


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def export_pl_report(request):
    from .exports import generate_pl_pdf, generate_pl_excel
    branch_id = request.query_params.get('branch')
    period = request.query_params.get('period', 'month')
    fmt = request.query_params.get('format', 'pdf')

    try:
        branch_name = Branch.objects.get(id=branch_id).name
    except Exception:
        branch_name = 'All Branches'

    report = get_pl_report_payload(branch_id, period)

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