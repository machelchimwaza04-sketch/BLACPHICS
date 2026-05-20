"""
Inventory system serializers with branch isolation and validation.
"""

from rest_framework import serializers
from .models import (
    InventoryTransaction, InventoryLedger, StockAdjustment,
    InventorySnapshot, InventorySnapshotItem
)
from common.mixins import StrictBranchSerializerMixin
from products.models import Product, ProductVariant
from suppliers.models import Purchase


class InventoryTransactionSerializer(StrictBranchSerializerMixin, serializers.ModelSerializer):
    """Serializer for inventory transactions."""

    product_name = serializers.CharField(source='product.name', read_only=True)
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    purchase_number = serializers.CharField(source='purchase.purchase_number', read_only=True)
    adjustment_number = serializers.CharField(source='adjustment.adjustment_number', read_only=True)

    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    completed_by_name = serializers.CharField(source='completed_by.get_full_name', read_only=True)

    class Meta:
        model = InventoryTransaction
        fields = '__all__'
        read_only_fields = [
            'transaction_number', 'status', 'approved_by', 'approved_at',
            'completed_by', 'completed_at'
        ]


class InventoryLedgerSerializer(StrictBranchSerializerMixin, serializers.ModelSerializer):
    """Serializer for inventory ledger entries."""

    product_name = serializers.CharField(source='product.name', read_only=True)
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    transaction_number = serializers.CharField(source='transaction.transaction_number', read_only=True)

    class Meta:
        model = InventoryLedger
        fields = '__all__'


class StockAdjustmentSerializer(StrictBranchSerializerMixin, serializers.ModelSerializer):
    """Serializer for stock adjustments with workflow validation."""

    product_name = serializers.CharField(source='product.name', read_only=True)
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    purchase_number = serializers.CharField(source='related_purchase.purchase_number', read_only=True)

    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    completed_by_name = serializers.CharField(source='completed_by.get_full_name', read_only=True)

    can_approve = serializers.SerializerMethodField()
    can_complete = serializers.SerializerMethodField()

    def get_can_approve(self, obj):
        """Check if current user can approve this adjustment."""
        request = self.context.get('request')
        if request and request.user:
            return obj.can_approve(request.user)
        return False

    def get_can_complete(self, obj):
        """Check if adjustment can be completed."""
        return obj.status == 'approved'

    class Meta:
        model = StockAdjustment
        fields = '__all__'
        read_only_fields = [
            'adjustment_number', 'adjustment_quantity', 'total_value_impact',
            'approved_by', 'approved_at', 'completed_by', 'completed_at'
        ]

    def validate(self, attrs):
        """Validate adjustment business rules."""
        status_val = attrs.get('status', self.instance.status if self.instance else 'draft')

        # Only certain fields can be updated based on status
        if self.instance and self.instance.status == 'completed':
            raise serializers.ValidationError("Completed adjustments cannot be modified")

        if self.instance and self.instance.status == 'approved' and status_val != 'completed':
            raise serializers.ValidationError("Approved adjustments can only be marked as completed")

        return attrs


class InventorySnapshotSerializer(StrictBranchSerializerMixin, serializers.ModelSerializer):
    """Serializer for inventory snapshots."""

    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    item_count = serializers.SerializerMethodField()

    def get_item_count(self, obj):
        return obj.items.count()

    class Meta:
        model = InventorySnapshot
        fields = '__all__'
        read_only_fields = ['created_by']


class InventorySnapshotItemSerializer(serializers.ModelSerializer):
    """Serializer for snapshot items."""

    product_name = serializers.CharField(source='product.name', read_only=True)
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    snapshot_date = serializers.DateTimeField(source='snapshot.snapshot_date', read_only=True)

    class Meta:
        model = InventorySnapshotItem
        fields = '__all__'


# =========================
# NESTED SERIALIZERS FOR COMPLEX OPERATIONS
# =========================

class StockAdjustmentCreateSerializer(StrictBranchSerializerMixin, serializers.ModelSerializer):
    """Serializer for creating stock adjustments."""

    class Meta:
        model = StockAdjustment
        fields = [
            'adjustment_type', 'product', 'variant', 'system_quantity',
            'actual_quantity', 'unit_cost', 'reason', 'notes', 'related_purchase'
        ]

    def validate(self, attrs):
        """Validate adjustment creation."""
        product = attrs['product']
        variant = attrs.get('variant')

        # Verify product belongs to branch
        if product.branch != self.get_branch():
            raise serializers.ValidationError("Product does not belong to your branch")

        # Get current system quantity
        if variant:
            current_quantity = variant.stock_quantity
        else:
            current_quantity = product.stock_quantity

        # If system_quantity not provided, use current
        if 'system_quantity' not in attrs:
            attrs['system_quantity'] = current_quantity

        # Validate quantities
        actual_quantity = attrs['actual_quantity']
        if actual_quantity < 0:
            raise serializers.ValidationError("Actual quantity cannot be negative")

        return attrs


class InventoryTransactionCreateSerializer(StrictBranchSerializerMixin, serializers.Serializer):
    """Serializer for creating inventory transactions via service."""

    transaction_type = serializers.ChoiceField(choices=InventoryTransaction.TRANSACTION_TYPES)
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.none(), required=False)
    variant = serializers.PrimaryKeyRelatedField(queryset=ProductVariant.objects.none(), required=False)
    quantity_change = serializers.IntegerField()
    unit_cost = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = serializers.CharField(required=False, allow_blank=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set querysets filtered by branch
        branch = self.get_branch()
        self.fields['product'].queryset = branch.products.all()
        self.fields['variant'].queryset = ProductVariant.objects.filter(product__branch=branch)

    def validate(self, attrs):
        """Validate transaction creation."""
        transaction_type = attrs['transaction_type']
        quantity_change = attrs['quantity_change']

        # Validate transaction type rules
        if transaction_type in ['sale', 'transfer_out'] and quantity_change > 0:
            raise serializers.ValidationError(f"{transaction_type} transactions must have negative quantity changes")

        if transaction_type in ['purchase_receipt', 'transfer_in'] and quantity_change < 0:
            raise serializers.ValidationError(f"{transaction_type} transactions must have positive quantity changes")

        # Validate stock availability for outgoing transactions
        if quantity_change < 0:
            product = attrs['product']
            variant = attrs.get('variant')
            abs_quantity = abs(quantity_change)

            if variant:
                if variant.available_quantity < abs_quantity:
                    raise serializers.ValidationError(f"Insufficient stock for {variant}")
            else:
                if product.stock_quantity < abs_quantity:
                    raise serializers.ValidationError(f"Insufficient stock for {product}")

        return attrs


class PurchaseReceiptSerializer(StrictBranchSerializerMixin, serializers.Serializer):
    """Serializer for processing purchase receipts."""

    purchase = serializers.PrimaryKeyRelatedField(queryset=Purchase.objects.none())
    received_items = serializers.ListField(
        child=serializers.DictField(
            child=serializers.IntegerField(min_value=0)
        )
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        branch = self.get_branch()
        self.fields['purchase'].queryset = branch.purchases.filter(status__in=['ordered', 'partially_received'])

    def validate(self, attrs):
        """Validate purchase receipt."""
        purchase = attrs['purchase']
        received_items = attrs['received_items']

        # Validate that all received items belong to the purchase
        purchase_item_ids = set(item.id for item in purchase.items.all())
        received_item_ids = set()

        for item_data in received_items:
            item_id = item_data.get('purchase_item')
            if item_id not in purchase_item_ids:
                raise serializers.ValidationError(f"Purchase item {item_id} does not belong to purchase {purchase.purchase_number}")
            received_item_ids.add(item_id)

        # Ensure all purchase items are accounted for
        if len(received_item_ids) != len(purchase_item_ids):
            missing_items = purchase_item_ids - received_item_ids
            raise serializers.ValidationError(f"Missing receipt data for purchase items: {missing_items}")

        return attrs


class InventorySnapshotCreateSerializer(StrictBranchSerializerMixin, serializers.Serializer):
    """Serializer for creating inventory snapshots."""

    snapshot_type = serializers.ChoiceField(choices=InventorySnapshot.SNAPSHOT_TYPES)
    physical_counts = serializers.DictField(
        child=serializers.IntegerField(min_value=0),
        required=False,
        help_text="Optional physical counts: {'product_1': 10, 'variant_2': 5}"
    )

    def validate_physical_counts(self, value):
        """Validate physical count keys."""
        branch = self.get_branch()

        for key, count in value.items():
            if key.startswith('product_'):
                product_id = key.split('_')[1]
                if not branch.products.filter(id=product_id).exists():
                    raise serializers.ValidationError(f"Product {product_id} does not belong to your branch")
            elif key.startswith('variant_'):
                variant_id = key.split('_')[1]
                if not ProductVariant.objects.filter(id=variant_id, product__branch=branch).exists():
                    raise serializers.ValidationError(f"Variant {variant_id} does not belong to your branch")
            else:
                raise serializers.ValidationError(f"Invalid key format: {key}")

        return value