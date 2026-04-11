from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, OrderItemViewSet, PaymentViewSet

router = DefaultRouter()
router.register(r'orders', OrderViewSet)
router.register(r'order-items', OrderItemViewSet)
router.register(r'payments', PaymentViewSet)

urlpatterns = [
    path('', include(router.urls)),
]