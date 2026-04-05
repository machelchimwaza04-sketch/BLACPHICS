from rest_framework import viewsets, filters
from .models import Category, Product, ProductVariant, CustomizationService
from .serializers import (
    CategorySerializer, ProductSerializer,
    ProductVariantSerializer, CustomizationServiceSerializer
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description', 'item_type']

    def get_queryset(self):
        queryset = Product.objects.all()
        branch = self.request.query_params.get('branch')
        if branch:
            queryset = queryset.filter(branch=branch)
        return queryset


class ProductVariantViewSet(viewsets.ModelViewSet):
    queryset = ProductVariant.objects.all()
    serializer_class = ProductVariantSerializer


class CustomizationServiceViewSet(viewsets.ModelViewSet):
    queryset = CustomizationService.objects.filter(is_active=True)
    serializer_class = CustomizationServiceSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']