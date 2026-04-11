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

    @action(detail=False, methods=['get'])
    def stats(self, request):
        branch = request.query_params.get('branch')
        now = timezone.now()
        month_ago = now - timedelta(days=30)

        current_qs = Product.objects.filter(branch=branch) if branch else Product.objects.all()
        prev_qs = Product.objects.filter(
            branch=branch, created_at__lt=month_ago
        ) if branch else Product.objects.filter(created_at__lt=month_ago)

        def get_stats(qs):
            variants = ProductVariant.objects.filter(product__in=qs)
            total_stock = sum(v.available_quantity for v in variants)
            low_stock = sum(
                1 for p in qs
                if any(
                    0 < v.available_quantity <= p.low_stock_threshold
                    for v in p.variants.all()
                )
            )
            out_of_stock = sum(
                1 for p in qs
                if all(v.available_quantity <= 0 for v in p.variants.all())
                and p.variants.exists()
            )
            return {
                'total_products': qs.count(),
                'total_stock': total_stock,
                'low_stock': low_stock,
                'out_of_stock': out_of_stock,
            }

        return Response({
            'current': get_stats(current_qs),
            'previous': get_stats(prev_qs),
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