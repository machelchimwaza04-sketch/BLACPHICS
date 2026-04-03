from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models
from rest_framework.permissions import AllowAny

from .models import Category, Product, ProductVariant
from .serializers import CategorySerializer, ProductSerializer, ProductVariantSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter
    ]

    search_fields = ['name', 'description', 'item_type']
    filterset_fields = ['branch', 'category', 'item_type', 'is_active']
    ordering_fields = ['base_price', 'stock_quantity', 'created_at']

    def get_queryset(self):
        queryset = Product.objects.all()

        branch = self.request.query_params.get('branch')
        if branch:
            queryset = queryset.filter(branch=branch)

        low_stock = self.request.query_params.get('low_stock')
        if low_stock == 'true':
            queryset = queryset.filter(
                stock_quantity__lte=models.F('low_stock_threshold')
            )

        return queryset


class ProductVariantViewSet(viewsets.ModelViewSet):
    queryset = ProductVariant.objects.all()
    serializer_class = ProductVariantSerializer