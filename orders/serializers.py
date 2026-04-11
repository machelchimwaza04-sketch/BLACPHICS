from rest_framework import serializers
from django.db.models import Sum
from .models import Order, OrderItem, Payment, Customer


# =========================================================
# PAYMENT SERIALIZER
# =========================================================
class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'


# =========================================================
# ORDER ITEM SERIALIZER
# =========================================================
class OrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.ReadOnlyField()
    
    class Meta:
        model = OrderItem
        fields = '__all__'


# =========================================================
# ORDER SERIALIZER (POS CORE)
# =========================================================
class OrderSerializer(serializers.ModelSerializer):
    # read_only=True is critical — items are created separately via /api/order-items/
    items = OrderItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    # Computed fields from model properties
    balance_due = serializers.ReadOnlyField()
    discounted_total = serializers.ReadOnlyField()
    change_due = serializers.ReadOnlyField()
    credit_balance = serializers.ReadOnlyField()
    is_quick_sale = serializers.ReadOnlyField()
    is_custom_order = serializers.ReadOnlyField()
    customer_name = serializers.SerializerMethodField()

    def get_customer_name(self, obj):
        if obj.customer:
            return f"{obj.customer.first_name} {obj.customer.last_name}"
        return None

    class Meta:
        model = Order
        fields = '__all__'

    # =====================================================
    # CREATE ORDER (FULLY INTEGRATED)
    # =====================================================
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        payments_data = validated_data.pop('payments', [])

        order = Order.objects.create(**validated_data)

        total = 0

        # =========================
        # CREATE ORDER ITEMS
        # =========================
        for item_data in items_data:
            item_serializer = OrderItemSerializer(
                data=item_data,
                context={'order': order}
            )
            item_serializer.is_valid(raise_exception=True)
            item = item_serializer.save(order=order)

            total += item.subtotal

        # =========================
        # UPDATE TOTAL
        # =========================
        order.total_amount = total
        order.save()

        # =========================
        # CREATE PAYMENTS
        # =========================
        total_paid = 0

        for payment_data in payments_data:
            payment = Payment.objects.create(order=order, **payment_data)
            total_paid += payment.amount

        # =========================
        # VALIDATION (OVERPAY PROTECTION)
        # =========================
        if total_paid > total:
            raise serializers.ValidationError(
                f"Total payment ({total_paid}) exceeds order total ({total})"
            )

        # =========================
        # FINAL STATUS UPDATE
        # =========================
        order.update_payment_status()
        order.save()

        return order

    # =====================================================
    # OPTIONAL: UPDATE ORDER
    # =====================================================
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        payments_data = validated_data.pop('payments', None)

        # Update order fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # =========================
        # UPDATE ITEMS (REPLACE)
        # =========================
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

        # =========================
        # UPDATE PAYMENTS (REPLACE)
        # =========================
        if payments_data is not None:
            instance.payments.all().delete()

            for payment_data in payments_data:
                Payment.objects.create(order=instance, **payment_data)

        instance.update_payment_status()
        instance.save()

        return instance


# =========================================================
# CUSTOMER ORDER SNAPSHOT (LIGHTWEIGHT)
# =========================================================
class CustomerOrderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order_number = serializers.CharField()
    transaction_type = serializers.CharField()
    status = serializers.CharField()
    payment_status = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2)
    balance_due = serializers.DecimalField(max_digits=10, decimal_places=2)
    created_at = serializers.DateTimeField()


# =========================================================
# CUSTOMER SERIALIZER (ANALYTICS LAYER)
# =========================================================
class CustomerSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    total_orders = serializers.IntegerField(source='orders.count', read_only=True)
    total_spent = serializers.SerializerMethodField()
    outstanding_balance = serializers.SerializerMethodField()
    recent_orders = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = '__all__'

    # =========================
    # FULL NAME
    # =========================
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    # =========================
    # TOTAL SPENT (OPTIMIZED)
    # =========================
    def get_total_spent(self, obj):
        return obj.orders.aggregate(
            total=Sum('amount_paid')
        )['total'] or 0

    # =========================
    # OUTSTANDING BALANCE
    # =========================
    def get_outstanding_balance(self, obj):
        return obj.orders.aggregate(
            total=Sum('balance_due')
        )['total'] or 0

    # =========================
    # RECENT ORDERS
    # =========================
    def get_recent_orders(self, obj):
        orders = obj.orders.order_by('-created_at')[:10]
        return CustomerOrderSerializer(orders, many=True).data