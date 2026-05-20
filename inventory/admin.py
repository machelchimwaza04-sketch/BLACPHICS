"""
Admin interface for Inventory Transaction & Ledger System.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    InventoryTransaction, InventoryLedger, StockAdjustment,
    InventorySnapshot, InventorySnapshotItem,
    InventoryTransactionSequence, StockAdjustmentSequence
)


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    """Admin for inventory transactions."""

    list_display = [
        'transaction_number', 'transaction_type', 'product', 'variant',
        'quantity_change', 'unit_cost', 'total_cost_value', 'status',
        'created_at', 'created_by'
    ]
    list_filter = [
        'transaction_type', 'status', 'branch', 'created_at',
        'product__category', 'created_by'
    ]
    search_fields = [
        'transaction_number', 'product__name', 'variant__size',
        'variant__color', 'notes'
    ]
    readonly_fields = [
        'transaction_number', 'approved_at', 'completed_at',
        'approved_by', 'completed_by'
    ]
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        """Filter by user's branch if not superuser."""
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(branch=request.user.branch)
        return qs

    def total_cost_value(self, obj):
        return f"${obj.total_cost_value}"
    total_cost_value.short_description = "Total Cost"


@admin.register(InventoryLedger)
class InventoryLedgerAdmin(admin.ModelAdmin):
    """Admin for inventory ledger entries."""

    list_display = [
        'transaction', 'entry_type', 'account_type', 'amount',
        'product', 'variant', 'created_at'
    ]
    list_filter = [
        'entry_type', 'account_type', 'branch', 'created_at',
        'product__category'
    ]
    search_fields = [
        'transaction__transaction_number', 'product__name',
        'variant__size', 'variant__color'
    ]
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        """Filter by user's branch if not superuser."""
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(branch=request.user.branch)
        return qs


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    """Admin for stock adjustments with workflow."""

    list_display = [
        'adjustment_number', 'adjustment_type', 'product', 'variant',
        'adjustment_quantity', 'total_value_impact', 'status',
        'created_by', 'created_at'
    ]
    list_filter = [
        'adjustment_type', 'status', 'branch', 'created_at',
        'product__category', 'created_by'
    ]
    search_fields = [
        'adjustment_number', 'product__name', 'variant__size',
        'variant__color', 'reason', 'notes'
    ]
    readonly_fields = [
        'adjustment_number', 'adjustment_quantity', 'total_value_impact',
        'approved_at', 'completed_at', 'approved_by', 'completed_by'
    ]
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'adjustment_number', 'adjustment_type', 'branch',
                'product', 'variant', 'status'
            )
        }),
        ('Quantities', {
            'fields': ('system_quantity', 'actual_quantity', 'adjustment_quantity')
        }),
        ('Financial Impact', {
            'fields': ('unit_cost', 'total_value_impact')
        }),
        ('Details', {
            'fields': ('reason', 'notes', 'related_purchase')
        }),
        ('Workflow', {
            'fields': (
                'created_by', 'approved_by', 'completed_by',
                'created_at', 'approved_at', 'completed_at'
            )
        }),
    )

    def get_queryset(self, request):
        """Filter by user's branch if not superuser."""
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(branch=request.user.branch)
        return qs

    def get_form(self, request, obj=None, **kwargs):
        """Customize form based on user permissions."""
        form = super().get_form(request, obj, **kwargs)

        # Disable certain fields based on status
        if obj and obj.status == 'completed':
            # Completed adjustments are read-only
            for field_name in form.base_fields:
                form.base_fields[field_name].disabled = True
        elif obj and obj.status == 'approved':
            # Approved adjustments can only be completed
            disabled_fields = [
                'adjustment_type', 'product', 'variant', 'system_quantity',
                'actual_quantity', 'unit_cost', 'reason', 'notes'
            ]
            for field_name in disabled_fields:
                if field_name in form.base_fields:
                    form.base_fields[field_name].disabled = True

        return form

    actions = ['approve_adjustments', 'reject_adjustments']

    def approve_adjustments(self, request, queryset):
        """Bulk approve adjustments."""
        approved_count = 0
        for adjustment in queryset:
            if adjustment.status == 'pending_approval' and adjustment.can_approve(request.user):
                try:
                    adjustment.approve(request.user)
                    approved_count += 1
                except Exception as e:
                    self.message_user(
                        request,
                        f"Failed to approve {adjustment.adjustment_number}: {e}",
                        level='ERROR'
                    )

        self.message_user(
            request,
            f"Successfully approved {approved_count} adjustments."
        )
    approve_adjustments.short_description = "Approve selected adjustments"

    def reject_adjustments(self, request, queryset):
        """Bulk reject adjustments."""
        rejected_count = 0
        for adjustment in queryset:
            if adjustment.status == 'pending_approval':
                adjustment.reject(request.user, "Bulk rejection via admin")
                rejected_count += 1

        self.message_user(
            request,
            f"Successfully rejected {rejected_count} adjustments."
        )
    reject_adjustments.short_description = "Reject selected adjustments"


@admin.register(InventorySnapshot)
class InventorySnapshotAdmin(admin.ModelAdmin):
    """Admin for inventory snapshots."""

    list_display = [
        'branch', 'snapshot_type', 'snapshot_date',
        'total_products', 'total_units', 'total_value',
        'low_stock_count', 'out_of_stock_count', 'created_by'
    ]
    list_filter = ['snapshot_type', 'branch', 'snapshot_date', 'created_by']
    search_fields = ['branch__name', 'notes']
    readonly_fields = [
        'total_products', 'total_variants', 'total_units', 'total_value',
        'low_stock_count', 'out_of_stock_count'
    ]
    date_hierarchy = 'snapshot_date'

    def get_queryset(self, request):
        """Filter by user's branch if not superuser."""
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(branch=request.user.branch)
        return qs


@admin.register(InventorySnapshotItem)
class InventorySnapshotItemAdmin(admin.ModelAdmin):
    """Admin for snapshot items."""

    list_display = [
        'snapshot', 'product', 'variant',
        'system_quantity', 'physical_quantity', 'variance_quantity',
        'unit_cost', 'total_value'
    ]
    list_filter = ['snapshot__snapshot_type', 'snapshot__branch']
    search_fields = ['product__name', 'variant__size', 'variant__color']
    readonly_fields = ['variance_quantity', 'variance_value']

    def get_queryset(self, request):
        """Filter by user's branch if not superuser."""
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(snapshot__branch=request.user.branch)
        return qs


# Sequence models - usually hidden from regular admin
@admin.register(InventoryTransactionSequence)
class InventoryTransactionSequenceAdmin(admin.ModelAdmin):
    """Admin for transaction number sequences."""
    list_display = ['branch', 'date', 'next_number']
    list_filter = ['branch', 'date']
    readonly_fields = ['branch', 'date']


@admin.register(StockAdjustmentSequence)
class StockAdjustmentSequenceAdmin(admin.ModelAdmin):
    """Admin for adjustment number sequences."""
    list_display = ['branch', 'date', 'next_number']
    list_filter = ['branch', 'date']
    readonly_fields = ['branch', 'date']