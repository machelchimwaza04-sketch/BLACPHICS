from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from .models import Category, Product, ProductVariant, CustomizationService
from .serializers import (
    CategorySerializer, ProductSerializer,
    ProductVariantSerializer, CustomizationServiceSerializer
)
from common.mixins import BranchScopedViewSetMixin
from common.selectors import ProductSelector


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ProductViewSet(BranchScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description', 'item_type']

    def get_queryset(self):
        branch_param = getattr(self, 'request', None) and self.request.query_params.get('branch')
        if self.request.user.is_admin and branch_param:
            queryset = ProductSelector.get_for_branch(branch_param)
        else:
            queryset = ProductSelector.get_queryset()
        return self.filter_queryset_by_branch(queryset)

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        branch_id = request.query_params.get('branch')
        products = Product.objects.filter(is_active=True)
        if branch_id:
            products = products.filter(branch_id=branch_id)

        variants = ProductVariant.objects.filter(product__in=products, is_available=True)
        total_stock = sum(
            max(0, (v.available_quantity if v.available_quantity is not None else v.stock_quantity) or 0)
            for v in variants
        )
        low_stock = sum(1 for v in variants if v.stock_status == 'low_stock')
        out_of_stock = sum(1 for v in variants if v.stock_status == 'out_of_stock')

        current = {
            'total_products': products.count(),
            'total_stock': total_stock,
            'low_stock': low_stock,
            'out_of_stock': out_of_stock,
        }
        return Response({
            'current': current,
            'previous': {**current, 'total_products': 0, 'total_stock': 0, 'low_stock': 0, 'out_of_stock': 0},
        })
    
    @action(detail=False, methods=['get'])
    def alerts(self, request):
        from .alerts import get_low_stock_alerts, send_low_stock_email
        branch_id = request.query_params.get('branch')
        send_email = request.query_params.get('send_email') == 'true'

        alerts = get_low_stock_alerts(branch_id=branch_id)

        if send_email and branch_id:
            from branches.models import Branch
            try:
                branch = Branch.objects.get(id=branch_id)
                send_low_stock_email(branch)
            except Branch.DoesNotExist:
                pass

        return Response({
            'count': len(alerts),
            'out_of_stock': sum(1 for a in alerts if a['status'] == 'out_of_stock'),
            'low_stock': sum(1 for a in alerts if a['status'] == 'low_stock'),
            'alerts': alerts,
        })


class ProductVariantViewSet(viewsets.ModelViewSet):
    queryset = ProductVariant.objects.all()
    serializer_class = ProductVariantSerializer


class CustomizationServiceViewSet(viewsets.ModelViewSet):
    queryset = CustomizationService.objects.filter(is_active=True)
    serializer_class = CustomizationServiceSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']