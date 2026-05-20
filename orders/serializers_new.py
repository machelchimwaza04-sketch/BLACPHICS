from rest_framework import serializers
from .models import Order, OrderItem, Payment
from common.mixins import StrictBranchSerializerMixin


class OrderItemSerializer(StrictBranchSerializerMixin, serializers.ModelSerializer):
    """Order item serializer with branch isolation."""

    product_name = serializers.CharField(source='product.name', read_only=True)
    variant_name = serializers.CharField(source='variant.name', read_only=True)

    class Meta:
        model = OrderItem
        fields = '__all__'
        read_only_fields = ['subtotal', 'final_unit_price', 'stock_status_at_order']

    def validate(self, attrs):
        """Validate order item belongs to correct branch."""
        order = attrs.get('order')
        if order and order.branch != self.get_branch():
            raise serializers.ValidationError("Order does not belong to your branch")
        return attrs


class PaymentSerializer(StrictBranchSerializerMixin, serializers.ModelSerializer):
    """Payment serializer with branch isolation."""

    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['processed_by']

    def validate(self, attrs):
        """Validate payment belongs to correct branch."""
        order = attrs.get('order')
        if order and order.branch != self.get_branch():
            raise serializers.ValidationError("Order does not belong to your branch")
        return attrs


class OrderSerializer(StrictBranchSerializerMixin, serializers.ModelSerializer):
    """
    Production-grade Order serializer with state management.
    """

    # Nested serializers
    items = OrderItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    # Computed fields
    balance_due = serializers.ReadOnlyField()
    discounted_total = serializers.ReadOnlyField()
    change_due = serializers.ReadOnlyField()
    credit_balance = serializers.ReadOnlyField()
    is_quick_sale = serializers.ReadOnlyField()
    is_custom_order = serializers.ReadOnlyField()

    # Customer info
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = [
            'order_number', 'status', 'payment_status', 'amount_paid',
            'created_at', 'updated_at', 'completed_at', 'cancelled_at',
            'completed_by', 'cancelled_by'
        ]

    def get_customer_name(self, obj):
        if obj.customer:
            return f"{obj.customer.first_name} {obj.customer.last_name}"
        return None

    def validate(self, attrs):
        """Validate order creation rules."""
        # Status validation
        status = attrs.get('status', 'draft')
        if status != 'draft':
            raise serializers.ValidationError("New orders must start as 'draft'")

        # Branch validation (inherited from mixin)
        return attrs

    def create(self, validated_data):
        """Order creation is handled by OrderService - this should not be called directly."""
        raise NotImplementedError("Use OrderService.create_order() instead")

    def update(self, instance, validated_data):
        """Update order with state validation."""
        if instance.is_final_state:
            raise serializers.ValidationError("Cannot modify completed/cancelled orders")

        # Only allow certain fields to be updated on non-final orders
        allowed_fields = ['notes', 'estimated_completion', 'discount_amount', 'discount_reason']
        for field in validated_data:
            if field not in allowed_fields:
                raise serializers.ValidationError(f"Cannot modify {field} on active orders")

        return super().update(instance, validated_data)