from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from common.branch_scope import BranchScopedQuerysetMixin
from .models import Supplier, Purchase, PurchaseItem
from .serializers import SupplierSerializer, PurchaseSerializer, PurchaseItemSerializer
from .selectors import supplier_summary_rows
from .services.purchase_service import PurchaseService


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'contact_person', 'email', 'phone']

    @action(detail=False, methods=['get'])
    def summary(self, request):
        return Response(supplier_summary_rows())

    @action(detail=True, methods=['get'])
    def purchases(self, request, pk=None):
        supplier = self.get_object()
        purchases = Purchase.objects.filter(supplier=supplier).order_by('-purchase_date')
        serializer = PurchaseSerializer(purchases, many=True)
        return Response(serializer.data)


class PurchaseViewSet(BranchScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Purchase.objects.all()
    serializer_class = PurchaseSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['purchase_number', 'status']

    def get_queryset(self):
        qs = super().get_queryset()
        supplier = self.request.query_params.get('supplier')
        if supplier:
            qs = qs.filter(supplier=supplier)
        return qs

    @action(detail=True, methods=['post'])
    def record_payment(self, request, pk=None):
        purchase = self.get_object()
        amount = float(request.data.get('amount', 0))
        try:
            updated = PurchaseService.record_payment(purchase, amount)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        return Response(PurchaseSerializer(updated).data)


class PurchaseItemViewSet(viewsets.ModelViewSet):
    queryset = PurchaseItem.objects.all()
    serializer_class = PurchaseItemSerializer