from rest_framework import viewsets, filters
from .models import Supplier, Purchase, PurchaseItem
from .serializers import SupplierSerializer, PurchaseSerializer, PurchaseItemSerializer


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'contact_person', 'email', 'phone']


class PurchaseViewSet(viewsets.ModelViewSet):
    queryset = Purchase.objects.all()
    serializer_class = PurchaseSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['purchase_number', 'status']

    def get_queryset(self):
        queryset = Purchase.objects.all()
        branch = self.request.query_params.get('branch')
        supplier = self.request.query_params.get('supplier')
        if branch:
            queryset = queryset.filter(branch=branch)
        if supplier:
            queryset = queryset.filter(supplier=supplier)
        return queryset


class PurchaseItemViewSet(viewsets.ModelViewSet):
    queryset = PurchaseItem.objects.all()
    serializer_class = PurchaseItemSerializer