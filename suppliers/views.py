from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count, F
from .models import Supplier, Purchase, PurchaseItem
from .serializers import SupplierSerializer, PurchaseSerializer, PurchaseItemSerializer


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'contact_person', 'email', 'phone']

    @action(detail=False, methods=['get'])
    def summary(self, request):
        suppliers = Supplier.objects.filter(is_active=True)
        data = []
        for s in suppliers:
            purchases = Purchase.objects.filter(supplier=s)
            total_owed = sum(
                float(p.total_amount) - float(p.amount_paid)
                for p in purchases
            )
            total_purchases = purchases.count()
            has_overdue = purchases.filter(
                payment_status__in=['unpaid', 'partial'],
                status='received'
            ).exists()
            data.append({
                'id': s.id,
                'name': s.name,
                'contact_person': s.contact_person,
                'phone': s.phone,
                'email': s.email,
                'total_owed': round(total_owed, 2),
                'total_purchases': total_purchases,
                'account_status': 'overdue' if has_overdue else 'clear' if total_owed == 0 else 'outstanding',
            })
        return Response(data)

    @action(detail=True, methods=['get'])
    def purchases(self, request, pk=None):
        supplier = self.get_object()
        purchases = Purchase.objects.filter(supplier=supplier).order_by('-purchase_date')
        serializer = PurchaseSerializer(purchases, many=True)
        return Response(serializer.data)


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

    @action(detail=True, methods=['post'])
    def record_payment(self, request, pk=None):
        purchase = self.get_object()
        amount = float(request.data.get('amount', 0))
        if amount <= 0:
            return Response({'error': 'Invalid amount'}, status=400)
        new_paid = float(purchase.amount_paid) + amount
        if new_paid >= float(purchase.total_amount):
            purchase.amount_paid = purchase.total_amount
            purchase.payment_status = 'paid'
        else:
            purchase.amount_paid = new_paid
            purchase.payment_status = 'partial'
        purchase.save()
        serializer = PurchaseSerializer(purchase)
        return Response(serializer.data)


class PurchaseItemViewSet(viewsets.ModelViewSet):
    queryset = PurchaseItem.objects.all()
    serializer_class = PurchaseItemSerializer