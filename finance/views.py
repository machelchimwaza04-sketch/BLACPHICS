from rest_framework import viewsets, filters
from .models import ExpenseCategory, Expense, Revenue, ProfitLossReport
from .serializers import (
    ExpenseCategorySerializer, ExpenseSerializer,
    RevenueSerializer, ProfitLossReportSerializer
)


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'description']

    def get_queryset(self):
        queryset = Expense.objects.all()
        branch = self.request.query_params.get('branch')
        if branch:
            queryset = queryset.filter(branch=branch)
        return queryset


class RevenueViewSet(viewsets.ModelViewSet):
    queryset = Revenue.objects.all()
    serializer_class = RevenueSerializer

    def get_queryset(self):
        queryset = Revenue.objects.all()
        branch = self.request.query_params.get('branch')
        if branch:
            queryset = queryset.filter(branch=branch)
        return queryset


class ProfitLossReportViewSet(viewsets.ModelViewSet):
    queryset = ProfitLossReport.objects.all()
    serializer_class = ProfitLossReportSerializer

    def get_queryset(self):
        queryset = ProfitLossReport.objects.all()
        branch = self.request.query_params.get('branch')
        if branch:
            queryset = queryset.filter(branch=branch)
        return queryset