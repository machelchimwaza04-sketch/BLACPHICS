"""
Base Selector classes for optimized data fetching and reporting.
Selectors encapsulate all read operations, ensuring consistent query optimization.
"""

from django.db.models import QuerySet, Prefetch, F


class BaseSelector:
    """Base class for all selectors."""
    
    @staticmethod
    def get_queryset():
        raise NotImplementedError('Subclasses must implement get_queryset()')


class OrderSelector(BaseSelector):
    """Optimized order queries."""
    
    @staticmethod
    def get_queryset():
        """Get orders with all related data pre-fetched."""
        from orders.models import Order, OrderItem, Payment
        
        return (
            Order.objects
            .select_related('customer', 'branch', 'created_by')
            .prefetch_related(
                Prefetch('items', queryset=OrderItem.objects.select_related('variant')),
                Prefetch('payments', queryset=Payment.objects.all())
            )
        )
    
    @staticmethod
    def get_for_branch(branch_id):
        """Get orders for a specific branch."""
        return OrderSelector.get_queryset().filter(branch_id=branch_id)
    
    @staticmethod
    def get_completed_orders(branch_id=None, start_date=None):
        """Get completed orders, optionally filtered by branch and start date."""
        qs = OrderSelector.get_queryset().filter(status='completed')
        
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        
        if start_date:
            qs = qs.filter(created_at__date__gte=start_date)
        
        return qs

    @staticmethod
    def get_paid_orders(branch_id=None):
        """Get orders with payment_status == 'paid'."""
        qs = OrderSelector.get_queryset().filter(payment_status='paid')
        
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        
        return qs


class CustomerSelector(BaseSelector):
    """Optimized customer queries."""
    
    @staticmethod
    def get_queryset():
        """Get customers with orders pre-fetched."""
        from customers.models import Customer
        from orders.models import Order
        
        return (
            Customer.objects
            .prefetch_related(
                Prefetch('orders', queryset=Order.objects.all().order_by('-created_at'))
            )
        )
    
    @staticmethod
    def get_for_branch(branch_id):
        """Get customers for a branch."""
        return CustomerSelector.get_queryset().filter(branch_id=branch_id)


class SupplierSelector(BaseSelector):
    """Optimized supplier queries."""
    
    @staticmethod
    def get_queryset():
        """Get suppliers with purchases pre-fetched."""
        from suppliers.models import Supplier, Purchase
        
        return (
            Supplier.objects
            .prefetch_related(
                Prefetch('purchases', queryset=Purchase.objects.all().order_by('-purchase_date'))
            )
        )
    
    @staticmethod
    def get_active_suppliers():
        """Get only active suppliers."""
        return SupplierSelector.get_queryset().filter(is_active=True)
    
    @staticmethod
    def get_with_summary():
        """Get suppliers with purchase summary data."""
        from suppliers.models import Supplier, Purchase
        from django.db.models import Sum, F, Case, When, Value, IntegerField, Count, DecimalField
        
        return (
            Supplier.objects.filter(is_active=True)
            .annotate(
                total_purchases=Count('purchases'),
                total_owed=Sum(
                    Case(
                        When(purchases__status='received', then=F('purchases__total_amount') - F('purchases__amount_paid')),
                        default=Value(0),
                        output_field=DecimalField(max_digits=14, decimal_places=2)
                    )
                ),
                has_overdue=Case(
                    When(
                        purchases__payment_status__in=['unpaid', 'partial'],
                        purchases__status='received',
                        then=Value(1)
                    ),
                    default=Value(0),
                    output_field=IntegerField()
                )
            )
        )


class ProductSelector(BaseSelector):
    """Optimized product queries."""
    
    @staticmethod
    def get_queryset():
        """Get products with variants and branch pre-fetched."""
        from products.models import Product, ProductVariant
        
        return (
            Product.objects
            .select_related('branch')
            .prefetch_related(
                Prefetch('variants', queryset=ProductVariant.objects.all())
            )
        )
    
    @staticmethod
    def get_for_branch(branch_id):
        """Get products for a specific branch."""
        return ProductSelector.get_queryset().filter(branch_id=branch_id)
    
    @staticmethod
    def get_with_stock_info(branch_id=None, created_after=None, created_before=None):
        """Get products with stock information and optional date filtering."""
        from products.models import ProductVariant
        
        qs = ProductSelector.get_queryset()
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        
        if created_after:
            qs = qs.filter(created_at__gte=created_after)
        
        if created_before:
            qs = qs.filter(created_at__lt=created_before)
        
        # Annotate with stock information
        return qs.prefetch_related(
            Prefetch('variants', 
                    queryset=ProductVariant.objects.annotate(
                        available_stock=F('stock_quantity') - F('committed_quantity')
                    ))
        )


class FinanceSelector(BaseSelector):
    """Optimized finance/reporting queries."""
    
    @staticmethod
    def get_expenses_for_period(branch_id=None, start_date=None, end_date=None):
        """Get expenses with category pre-fetched."""
        from finance.models import Expense
        
        qs = Expense.objects.select_related('category', 'branch')
        
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        
        if start_date:
            qs = qs.filter(date__gte=start_date)
        
        if end_date:
            qs = qs.filter(date__lte=end_date)
        
        return qs
    
    @staticmethod
    def get_revenue_for_period(branch_id=None, start_date=None, end_date=None):
        """Get revenue items."""
        from finance.models import Revenue
        
        qs = Revenue.objects.select_related('branch')
        
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        
        if start_date:
            qs = qs.filter(date__gte=start_date)
        
        if end_date:
            qs = qs.filter(date__lte=end_date)
        
        return qs
