from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count, F
from django.core.exceptions import ValidationError
from common.mixins import BranchScopedViewSetMixin
from .models import Supplier, Purchase, PurchaseItem
from .serializers import SupplierSerializer, PurchaseSerializer, PurchaseItemSerializer
from .services import SupplierService
from common.selectors import SupplierSelector


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = SupplierSelector.get_queryset()
    serializer_class = SupplierSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'contact_person', 'email', 'phone']

    def get_queryset(self):
        return SupplierSelector.get_queryset()

    @action(detail=False, methods=['get'])
    def summary(self, request):
        suppliers = SupplierSelector.get_with_summary()
        data = []
        for s in suppliers:
            total_owed = float(s.total_owed or 0)
            has_overdue = bool(s.has_overdue)
            data.append({
                'id': s.id,
                'name': s.name,
                'contact_person': s.contact_person,
                'phone': s.phone,
                'email': s.email,
                'total_owed': round(total_owed, 2),
                'total_purchases': s.total_purchases,
                'account_status': 'overdue' if has_overdue else 'clear' if total_owed == 0 else 'outstanding',
            })
        return Response(data)

    @action(detail=True, methods=['get'])
    def purchases(self, request, pk=None):
        supplier = self.get_object()
        purchases = Purchase.objects.filter(supplier=supplier).order_by('-purchase_date')
        serializer = PurchaseSerializer(purchases, many=True)
        return Response(serializer.data)


class PurchaseViewSet(BranchScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Purchase.objects.all()
    serializer_class = PurchaseSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['purchase_number', 'status']

    def get_queryset(self):
        queryset = Purchase.objects.all()
        if self.request.user.is_admin and self.request.query_params.get('branch'):
            queryset = queryset.filter(branch=self.request.query_params.get('branch'))
        queryset = self.filter_queryset_by_branch(queryset)

        supplier = self.request.query_params.get('supplier')
        if supplier:
            queryset = queryset.filter(supplier=supplier)
        return queryset

    @action(detail=True, methods=['post'])
    def record_payment(self, request, pk=None):
        purchase = self.get_object()
        amount = float(request.data.get('amount', 0))
        reference = request.data.get('reference')
        notes = request.data.get('notes', '')

        if amount <= 0:
            return Response({'error': 'Invalid amount'}, status=400)

        try:
            purchase, payment_record = SupplierService.record_purchase_payment(
                purchase=purchase,
                amount=amount,
                processed_by=request.user,
                reference=reference,
                notes=notes
            )
            serializer = PurchaseSerializer(purchase)
            return Response({
                'purchase': serializer.data,
                'payment_id': payment_record.id,
                'payment_amount': float(payment_record.amount),
                'payment_reference': payment_record.reference,
            })
        except ValidationError as e:
            return Response({'error': str(e)}, status=400)


class PurchaseItemViewSet(viewsets.ModelViewSet):
    queryset = PurchaseItem.objects.all()
    serializer_class = PurchaseItemSerializer