from rest_framework import serializers
from .models import Order, OrderItem
from products.models import ProductVariant


# =========================================================
# ORDER ITEM SERIALIZER
# =========================================================
class OrderItemSerializer(serializers.ModelSerializer):

    # 🔥 Computed fields
    subtotal = serializers.ReadOnlyField()
    stock_status = serializers.SerializerMethodField()
    available_quantity = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = '__all__'

    # =========================
    # STOCK INTELLIGENCE
    # =========================
    def get_stock_status(self, obj):
        if obj.variant:
            return obj.variant.stock_status
        return 'in_stock'

    def get_available_quantity(self, obj):
        if obj.variant:
            return obj.variant.available_quantity
        return None

    # =========================
    # VALIDATION (CRITICAL)
    # =========================
    def validate(self, data):
        order = self.context.get('order')  # passed from parent serializer
        variant = data.get('variant')
        quantity = data.get('quantity', 0)

        if order and order.transaction_type == 'quick_sale' and variant:
            available = variant.available_quantity
            if quantity > available:
                raise serializers.ValidationError(
                    f"Only {available} units available. Use Custom Order."
                )

        return data


# =========================================================
# ORDER SERIALIZER
# =========================================================
class OrderSerializer(serializers.ModelSerializer):

    items = OrderItemSerializer(many=True)
    
    # 🔥 Computed fields
    balance_due = serializers.ReadOnlyField()
    discounted_total = serializers.ReadOnlyField()
    is_quick_sale = serializers.ReadOnlyField()
    is_custom_order = serializers.ReadOnlyField()

    class Meta:
        model = Order
        fields = '__all__'

    # =====================================================
    # CREATE ORDER WITH ITEMS (POS CORE)
    # =====================================================
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])

        order = Order.objects.create(**validated_data)

        total = 0

        for item_data in items_data:
            variant = item_data.get('variant')
            quantity = item_data.get('quantity', 1)

            # Ensure context for validation
            serializer = OrderItemSerializer(
                data=item_data,
                context={'order': order}
            )
            serializer.is_valid(raise_exception=True)

            item = serializer.save(order=order)

            total += item.subtotal

        # Update total
        order.total_amount = total
        order.update_payment_status()
        order.save()

        return order

    # =====================================================
    # UPDATE ORDER (SAFE)
    # =====================================================
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)

        # Update order fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Optional: handle items update (simple version)
        if items_data is not None:
            instance.items.all().delete()

            total = 0

            for item_data in items_data:
                serializer = OrderItemSerializer(
                    data=item_data,
                    context={'order': instance}
                )
                serializer.is_valid(raise_exception=True)

                item = serializer.save(order=instance)
                total += item.subtotal

            instance.total_amount = total

        instance.update_payment_status()
        instance.save()

        return instance