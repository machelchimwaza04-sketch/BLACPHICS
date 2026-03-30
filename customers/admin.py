from django.contrib import admin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'branch', 'phone', 'email', 'gender', 'is_active', 'created_at']
    list_filter = ['branch', 'gender', 'is_active']
    search_fields = ['first_name', 'last_name', 'email', 'phone']
    list_editable = ['is_active']
    ordering = ['first_name', 'last_name']