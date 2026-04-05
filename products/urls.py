from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, ProductViewSet,
    ProductVariantViewSet, CustomizationServiceViewSet
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'products', ProductViewSet)
router.register(r'variants', ProductVariantViewSet)
router.register(r'customization-services', CustomizationServiceViewSet)

urlpatterns = [
    path('', include(router.urls)),
]