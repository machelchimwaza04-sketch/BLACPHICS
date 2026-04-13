from rest_framework import serializers
from .models import ExpenseCategory, Expense, Revenue, ProfitLossReport


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = '__all__'


class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)

    class Meta:
        model = Expense
        fields = [
            'id', 'branch', 'category', 'category_name', 'title', 'description',
            'amount', 'date', 'receipt', 'created_at', 'updated_at',
        ]

    def to_internal_value(self, data):
        d = data.copy() if hasattr(data, 'copy') else dict(data)
        if not d.get('title') and d.get('description'):
            d['title'] = d['description']
        return super().to_internal_value(d)


class RevenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Revenue
        fields = '__all__'


class ProfitLossReportSerializer(serializers.ModelSerializer):
    net_profit = serializers.ReadOnlyField()
    is_profitable = serializers.ReadOnlyField()

    class Meta:
        model = ProfitLossReport
        fields = '__all__'