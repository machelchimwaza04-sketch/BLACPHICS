from django.contrib import admin
from .models import ExpenseCategory, Expense, Revenue, ProfitLossReport


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['title', 'branch', 'category', 'amount', 'date', 'created_at']
    list_filter = ['branch', 'category', 'date']
    search_fields = ['title', 'description']
    ordering = ['-date']


@admin.register(Revenue)
class RevenueAdmin(admin.ModelAdmin):
    list_display = ['source', 'branch', 'amount', 'date', 'description', 'created_at']
    list_filter = ['branch', 'source', 'date']
    search_fields = ['description']
    ordering = ['-date']


@admin.register(ProfitLossReport)
class ProfitLossReportAdmin(admin.ModelAdmin):
    list_display = ['branch', 'period', 'start_date', 'end_date', 'total_revenue', 'total_expenses', 'net_profit', 'is_profitable']
    list_filter = ['branch', 'period']
    ordering = ['-start_date']