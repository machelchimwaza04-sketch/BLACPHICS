from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ExpenseCategoryViewSet, ExpenseViewSet,
    RevenueViewSet, ProfitLossReportViewSet
)

router = DefaultRouter()
router.register(r'expense-categories', ExpenseCategoryViewSet)
router.register(r'expenses', ExpenseViewSet)
router.register(r'revenue', RevenueViewSet)
router.register(r'reports', ProfitLossReportViewSet)

urlpatterns = [
    path('', include(router.urls)),
]