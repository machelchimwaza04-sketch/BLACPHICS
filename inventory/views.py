"""
Production-grade Inventory API views.

Provides REST endpoints for:
- Inventory transaction management
- Stock adjustment workflow
- Inventory snapshots and reconciliation
- Reporting and analytics
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, F, Q
from django.utils import timezone
from decimal import Decimal
from .models import (
    InventoryTransaction, InventoryLedger, StockAdjustment,
    InventorySnapshot, InventorySnapshotItem
)
from .serializers import (
    InventoryTransactionSerializer, InventoryLedgerSerializer,
    StockAdjustmentSerializer, InventorySnapshotSerializer,
    InventorySnapshotItemSerializer
)
from .services import InventoryService
from common.mixins import BranchScopedViewSetMixin


class InventoryTransactionViewSet(BranchScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Read-only view for inventory transactions.
    Transactions are created by the service layer, not directly via API.
    """
    queryset = InventoryTransaction.objects.all()
    serializer_class = InventoryTransactionSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['transaction_type', 'status', 'product', 'variant']
    search_fields = ['transaction_number', 'notes']
    ordering_fields = ['created_at', 'completed_at']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter by branch and apply additional filters."""
        queryset = InventoryTransaction.objects.filter(branch=self.get_branch())

        # Date range filter
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)

        return queryset

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get inventory transaction summary for date range."""
        queryset = self.get_queryset()

        summary = queryset.aggregate(
            total_transactions=models.Count('id'),
            stock_in_total=Sum(
                models.Case(
                    models.When(quantity_change__gt=0, then=F('quantity_change')),
                    default=0,
                    output_field=models.IntegerField()
                )
            ),
            stock_out_total=Sum(
                models.Case(
                    models.When(quantity_change__lt=0, then=F('quantity_change')),
                    default=0,
                    output_field=models.IntegerField()
                )
            ),
            total_value=Sum(
                models.Case(
                    models.When(quantity_change__gt=0, then=F('quantity_change') * F('unit_cost')),
                    default=0,
                    output_field=models.DecimalField()
                )
            )
        )

        return Response(summary)


class InventoryLedgerViewSet(BranchScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Read-only view for inventory ledger entries.
    """
    queryset = InventoryLedger.objects.all()
    serializer_class = InventoryLedgerSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['entry_type', 'account_type', 'product', 'variant']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter by branch."""
        return InventoryLedger.objects.filter(branch=self.get_branch())

    @action(detail=False, methods=['get'])
    def account_summary(self, request):
        """Get ledger summary by account type."""
        queryset = self.get_queryset()

        # Group by account type and entry type
        summary = {}
        for entry in queryset:
            account = entry.account_type
            if account not in summary:
                summary[account] = {'debit': Decimal('0.00'), 'credit': Decimal('0.00')}

            if entry.entry_type == 'debit':
                summary[account]['debit'] += entry.amount
            else:
                summary[account]['credit'] += entry.amount

        # Calculate balances
        for account, amounts in summary.items():
            amounts['balance'] = amounts['debit'] - amounts['credit']

        return Response(summary)


class StockAdjustmentViewSet(BranchScopedViewSetMixin, viewsets.ModelViewSet):
    """
    Full CRUD for stock adjustments with approval workflow.
    """
    queryset = StockAdjustment.objects.all()
    serializer_class = StockAdjustmentSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['adjustment_type', 'status', 'product', 'variant']
    search_fields = ['adjustment_number', 'reason', 'notes']
    ordering_fields = ['created_at', 'approved_at', 'completed_at']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter by branch."""
        return StockAdjustment.objects.filter(branch=self.get_branch())

    def perform_create(self, serializer):
        """Set created_by on creation."""
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def submit_for_approval(self, request, pk=None):
        """Submit adjustment for approval."""
        adjustment = self.get_object()

        if adjustment.status != 'draft':
            return Response(
                {'error': 'Only draft adjustments can be submitted for approval'},
                status=status.HTTP_400_BAD_REQUEST
            )

        adjustment.status = 'pending_approval'
        adjustment.save()

        serializer = self.get_serializer(adjustment)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve adjustment."""
        adjustment = self.get_object()

        try:
            adjustment.approve(request.user)
            serializer = self.get_serializer(adjustment)
            return Response(serializer.data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject adjustment."""
        adjustment = self.get_object()
        reason = request.data.get('reason', '')

        if not reason:
            return Response(
                {'error': 'Rejection reason required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            adjustment.reject(request.user, reason)
            serializer = self.get_serializer(adjustment)
            return Response(serializer.data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete approved adjustment."""
        adjustment = self.get_object()

        try:
            InventoryService.process_stock_adjustment(adjustment, request.user)
            serializer = self.get_serializer(adjustment)
            return Response(serializer.data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class InventorySnapshotViewSet(BranchScopedViewSetMixin, viewsets.ModelViewSet):
    """
    Inventory snapshots for reconciliation and reporting.
    """
    queryset = InventorySnapshot.objects.all()
    serializer_class = InventorySnapshotSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['snapshot_type']
    ordering_fields = ['snapshot_date']
    ordering = ['-snapshot_date']

    def get_queryset(self):
        """Filter by branch."""
        return InventorySnapshot.objects.filter(branch=self.get_branch())

    def perform_create(self, serializer):
        """Set created_by on creation."""
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['post'])
    def create_snapshot(self, request):
        """Create new inventory snapshot."""
        snapshot_type = request.data.get('snapshot_type', 'manual')
        physical_counts = request.data.get('physical_counts', {})

        try:
            snapshot = InventoryService.create_inventory_snapshot(
                branch=self.get_branch(),
                snapshot_type=snapshot_type,
                created_by=request.user,
                physical_counts=physical_counts
            )

            serializer = self.get_serializer(snapshot)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def variance_report(self, request, pk=None):
        """Get variance report for snapshot."""
        snapshot = self.get_object()

        # Get items with variances
        variance_items = snapshot.items.filter(
            physical_quantity__isnull=False
        ).exclude(
            variance_quantity=0
        ).order_by('-variance_value')

        data = {
            'snapshot': self.get_serializer(snapshot).data,
            'variance_summary': {
                'total_items_with_variance': variance_items.count(),
                'total_variance_value': variance_items.aggregate(
                    total=Sum('variance_value')
                )['total'] or Decimal('0.00')
            },
            'variance_items': InventorySnapshotItemSerializer(variance_items, many=True).data
        }

        return Response(data)


class InventorySnapshotItemViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only view for snapshot items.
    """
    queryset = InventorySnapshotItem.objects.all()
    serializer_class = InventorySnapshotItemSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['snapshot', 'product', 'variant']

    @action(detail=False, methods=['get'])
    def current_stock(self, request):
        """Get current stock levels for reconciliation."""
        branch = request.user.branch

        # This would need to be implemented to return current stock
        # Similar to snapshot creation logic
        return Response({'message': 'Current stock endpoint - to be implemented'})


# =========================
# REPORTING VIEWS
# =========================

class InventoryReportsViewSet(BranchScopedViewSetMixin, viewsets.ViewSet):
    """
    Inventory reporting endpoints.
    """

    @action(detail=False, methods=['get'])
    def valuation(self, request):
        """Get inventory valuation report."""
        valuation_method = request.query_params.get('method', 'fifo')

        try:
            valuation = InventoryService.get_inventory_valuation(
                self.get_branch(), valuation_method
            )
            return Response(valuation)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def turnover(self, request):
        """Get inventory turnover report."""
        period_days = int(request.query_params.get('period_days', 30))

        try:
            turnover = InventoryService.get_inventory_turnover(
                self.get_branch(), period_days
            )
            return Response(turnover)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def stock_status(self, request):
        """Get stock status summary."""
        branch = self.get_branch()

        # Get product stock status
        products = branch.products.all()
        product_stats = {
            'total_products': products.count(),
            'in_stock': products.filter(stock_quantity__gt=0).count(),
            'low_stock': products.filter(
                stock_quantity__lte=F('low_stock_threshold'),
                stock_quantity__gt=0
            ).count(),
            'out_of_stock': products.filter(stock_quantity=0).count(),
        }

        # Get variant stock status
        from products.models import ProductVariant
        variants = ProductVariant.objects.filter(product__branch=branch)
        variant_stats = {
            'total_variants': variants.count(),
            'in_stock': variants.filter(stock_status='in_stock').count(),
            'low_stock': variants.filter(stock_status='low_stock').count(),
            'out_of_stock': variants.filter(stock_status='out_of_stock').count(),
        }

        return Response({
            'products': product_stats,
            'variants': variant_stats,
            'generated_at': timezone.now()
        })

    @action(detail=False, methods=['get'])
    def transaction_summary(self, request):
        """Get transaction summary by type and period."""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        queryset = InventoryTransaction.objects.filter(branch=self.get_branch())

        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)

        # Group by transaction type
        summary = {}
        for transaction_type_val, _ in InventoryTransaction.TRANSACTION_TYPES:
            type_queryset = queryset.filter(transaction_type=transaction_type_val)
            summary[transaction_type_val] = {
                'count': type_queryset.count(),
                'total_quantity': type_queryset.aggregate(
                    total=Sum('quantity_change')
                )['total'] or 0,
                'total_value': type_queryset.aggregate(
                    total=Sum(
                        models.Case(
                            models.When(quantity_change__gt=0, then=F('quantity_change') * F('unit_cost')),
                            default=0,
                            output_field=models.DecimalField()
                        )
                    )
                )['total'] or Decimal('0.00')
            }

        return Response({
            'period': {'start_date': start_date, 'end_date': end_date},
            'summary': summary,
            'generated_at': timezone.now()
        })