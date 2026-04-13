from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ExpenseCategoryViewSet, ExpenseViewSet, RevenueViewSet, export_pl_report, export_orders_report

router = DefaultRouter()
router.register(r'expense-categories', ExpenseCategoryViewSet)
router.register(r'expenses', ExpenseViewSet)
router.register(r'revenue', RevenueViewSet)

urlpatterns = [
    # Export endpoints MUST come before the router include
    # because router catches all unmatched paths
    path('export/pl/', export_pl_report, name='export-pl'),
    path('export/orders/', export_orders_report, name='export-orders'),
    # Router endpoints
    path('', include(router.urls)),
]