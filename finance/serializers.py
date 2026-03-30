from rest_framework import serializers
from .models import ExpenseCategory, Expense, Revenue, ProfitLossReport


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = '__all__'


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = '__all__'


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