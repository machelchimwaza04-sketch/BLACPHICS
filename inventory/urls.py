"""
URL configuration for Inventory Transaction & Ledger System.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router for ViewSets
router = DefaultRouter()
router.register(r'transactions', views.InventoryTransactionViewSet, basename='inventory-transaction')
router.register(r'ledger', views.InventoryLedgerViewSet, basename='inventory-ledger')
router.register(r'adjustments', views.StockAdjustmentViewSet, basename='stock-adjustment')
router.register(r'snapshots', views.InventorySnapshotViewSet, basename='inventory-snapshot')
router.register(r'snapshot-items', views.InventorySnapshotItemViewSet, basename='inventory-snapshot-item')
router.register(r'reports', views.InventoryReportsViewSet, basename='inventory-reports')

# URL patterns
urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),

    # Additional endpoints can be added here
]