"""
OrderService: Encapsulates all order business logic.
Ensures consistency whether orders are created via POS, API, or background processes.
"""

from decimal import Decimal
from django.db import transaction
from django.db.models import F, Sum
from orders.models import Order, OrderItem, Payment


class OrderService:
    """
    Service layer for order operations.
    Handles:
    - Race-condition-safe stock deductions
    - Payment recording and reconciliation
    - Order status transitions
    """
    
    @staticmethod
    @transaction.atomic
    def create_order(branch, customer=None, items_data=None, payments_data=None, **kwargs):
        """
        Create an order with items and payments atomically.
        
        Uses select_for_update() for row-level locking to prevent race conditions.
        """
        if items_data is None:
            items_data = []
        if payments_data is None:
            payments_data = []
        
        order = Order.objects.create(
            branch=branch,
            customer=customer,
            **kwargs
        )
        
        total_amount = Decimal('0.00')
        
        # Create order items and deduct stock safely
        for item_data in items_data:
            variant = item_data.get('variant')
            quantity = Decimal(str(item_data.get('quantity', 0)))
            unit_price = Decimal(str(item_data.get('unit_price', 0)))
            
            # Lock the variant row to prevent concurrent stock updates
            if variant:
                variant = type(variant).objects.select_for_update().get(pk=variant.pk)
                
                # Check stock availability
                if variant.stock < quantity:
                    raise ValueError(f"Insufficient stock for {variant.sku}")
                
                # Deduct stock using F() expressions for atomicity
                type(variant).objects.filter(pk=variant.pk).update(stock=F('stock') - quantity)
            
            item = OrderItem.objects.create(
                order=order,
                variant=variant,
                quantity=quantity,
                unit_price=unit_price
            )
            
            total_amount += item.subtotal
        
        # Update order total only when items are provided.
        if items_data:
            order.total_amount = total_amount
            order.save()
        
        # Record payments
        total_paid = Decimal('0.00')
        for payment_data in payments_data:
            amount = Decimal(str(payment_data.get('amount', 0)))
            payment_payload = {**payment_data, 'amount': amount}
            payment = Payment.objects.create(order=order, **payment_payload)
            total_paid += amount
        
        # Validate: payments should not exceed order total
        order_total = order.total_amount
        if total_paid > order_total:
            raise ValueError(f"Total payments ({total_paid}) exceed order total ({order_total})")
        
        # Update payment totals and status
        order.recalculate_payment_status()
        
        return order
    
    @staticmethod
    @transaction.atomic
    def add_payment_to_order(order, amount, method='cash', notes=''):
        """
        Add a payment to an order safely.
        Recalculates balance and status.
        """
        amount = Decimal(str(amount))
        
        if amount <= 0:
            raise ValueError("Payment amount must be positive")
        
        # Lock order row
        order = Order.objects.select_for_update().get(pk=order.pk)
        order.recalculate_payment_status()
        
        # Check overpayment
        if amount > order.balance_due:
            raise ValueError(f"Payment exceeds remaining balance ({order.balance_due})")
        
        payment = Payment.objects.create(
            order=order,
            amount=amount,
            method=method,
            notes=notes
        )
        
        # Refresh and update status
        order.refresh_from_db()
        order.recalculate_payment_status()
        
        return payment
    
    @staticmethod
    @transaction.atomic
    def writeoff_order_balance(order, notes=''):
        """
        Write off the remaining balance of an order.
        """
        order = Order.objects.select_for_update().get(pk=order.pk)
        order.recalculate_payment_status()
        balance = order.balance_due
        
        if balance <= 0:
            raise ValueError("No balance to write off")
        
        payment = Payment.objects.create(
            order=order,
            amount=balance,
            method='writeoff',
            payment_type='writeoff',
            notes=notes or 'Written off'
        )
        
        order.refresh_from_db()
        order.recalculate_payment_status()
        
        return payment
