from rest_framework import serializers
from .models import Customer


class CustomerOrderSerializer(serializers.Serializer):
    """
    Lightweight snapshot of an order attached to a customer.
    Used inside CustomerSerializer.get_recent_orders.
    balance_due is a model property (not a DB field) so we use FloatField.
    """
    id = serializers.IntegerField()
    order_number = serializers.CharField()
    transaction_type = serializers.CharField()
    status = serializers.CharField()
    payment_status = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2)
    balance_due = serializers.FloatField()
    created_at = serializers.DateTimeField()


class CustomerSerializer(serializers.ModelSerializer):
    """
    Full customer serializer with analytics:
    - full_name: first + last
    - total_orders: count of all orders
    - total_spent: sum of amount_paid across all orders
    - outstanding_balance: sum of unpaid balances across all orders
    - recent_orders: last 10 orders as lightweight snapshots
    """
    full_name = serializers.SerializerMethodField()
    total_orders = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()
    outstanding_balance = serializers.SerializerMethodField()
    recent_orders = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = '__all__'

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_total_orders(self, obj):
        return obj.orders.count()

    def get_total_spent(self, obj):
        return sum(float(o.amount_paid) for o in obj.orders.all())

    def get_outstanding_balance(self, obj):
        return sum(
            max(0, float(o.balance_due))
            for o in obj.orders.all()
        )

    def get_recent_orders(self, obj):
        orders = obj.orders.order_by('-created_at')[:10]
        return CustomerOrderSerializer(orders, many=True).data