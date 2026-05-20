"""
OrderService: Production-grade service layer for Order business logic.
Handles all transactional operations with proper state management and concurrency control.
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from .models import Order, OrderItem, Payment, OrderNumberSequence, StockReservation
from products.models import ProductVariant
from inventory.services import InventoryService
from finance import services as finance_services
from common.locking import get_order_lock


class OrderService:
    """
    Centralized service layer for all Order business logic.
    Handles transactions, state management, and stock operations.
    """

    # =========================
    # ORDER CREATION
    # =========================
    @staticmethod
    @transaction.atomic
    def create_order(branch, created_by, transaction_type='quick_sale', items_data=None, payments_data=None, **order_data):
        """
        Create order and optionally attach items and payments.
        """
        order_number = OrderNumberSequence.generate_order_number(branch)
        order = Order.objects.create(
            branch=branch,
            order_number=order_number,
            transaction_type=transaction_type,
            created_by=created_by,
            **order_data
        )

        items_data = items_data or []
        payments_data = payments_data or []

        for item_data in items_data:
            OrderService.add_order_item(
                order=order,
                product=item_data['product'],
                quantity=item_data.get('quantity', 1),
                variant=item_data.get('variant'),
                **{k: v for k, v in item_data.items() if k not in ['product', 'quantity', 'variant']}
            )

        for payment_data in payments_data:
            PaymentService.add_payment(
                order=order,
                amount=Decimal(payment_data['amount']),
                method=payment_data.get('method', 'cash'),
                processed_by=created_by,
                reference=payment_data.get('reference'),
                payment_type=payment_data.get('payment_type', 'payment'),
                notes=payment_data.get('notes', ''),
            )

        return order

    @staticmethod
    def generate_order_number(branch):
        return OrderNumberSequence.generate_order_number(branch)

    @staticmethod
    @transaction.atomic
    def add_order_item(order, product, quantity, variant=None, **item_data):
        if order.status in ['completed', 'cancelled']:
            raise ValidationError("Cannot add items to completed or cancelled orders")

        if variant:
            variant = ProductVariant.objects.select_for_update().get(pk=variant.pk)
            available_quantity = variant.available_quantity
        else:
            raise ValidationError("Order items must reference a product variant")

        if quantity > available_quantity:
            raise ValidationError(
                f"Insufficient stock for {product.name}. Available: {available_quantity}"
            )

        unit_price = item_data.get('unit_price') or variant.selling_price or product.base_price
        item = OrderItem.objects.create(
            order=order,
            product=product,
            variant=variant,
            quantity=quantity,
            unit_price=unit_price,
            **item_data
        )

        OrderService._recalculate_order_total(order)
        return item

    # =========================
    # ORDER STATE MANAGEMENT
    # =========================
    @staticmethod
    @transaction.atomic
    def confirm_order(order, user, ttl_hours=4):
        OrderService._validate_order_branch(order, user)

        if order.status != 'pending':
            raise ValidationError(f"Cannot confirm order in status: {order.status}")

        if order.is_custom_order:
            OrderService._reserve_order_stock(order, user, ttl_hours=ttl_hours)

        order.status = 'confirmed'
        order.save(update_fields=['status', 'updated_at'])
        return order

    @staticmethod
    @transaction.atomic
    def complete_order(order, user):
        OrderService._validate_order_branch(order, user)

        if order.status in ['completed', 'cancelled']:
            raise ValidationError(f"Cannot complete order in status: {order.status}")

        # Acquire distributed lock for order operations
        with get_order_lock(order.id):
            if order.is_custom_order and order.stock_reservations.filter(active=True).exists():
                OrderService._release_order_reservations(order, user)

            InventoryService.process_order_completion(order, user)

            if order.deposit_amount > 0:
                deposit_application = min(order.deposit_amount, order.discounted_total)
                if deposit_application > 0:
                    finance_services.apply_customer_deposit(
                        branch=order.branch,
                        created_by=user,
                        amount=deposit_application,
                        reference=f"APPLYDEP-{order.order_number}",
                        description=f"Apply customer deposit for order {order.order_number}",
                    )

            finance_services.record_sale_revenue(
                branch=order.branch,
                created_by=user,
                amount=order.discounted_total,
                reference=f"SALE-{order.order_number}",
                description=f"Recognize revenue for order {order.order_number}",
                source_document_type='Order',
                source_document_id=str(order.id),
            )

            order.status = 'completed'
            order.completed_by = user
            order.completed_at = timezone.now()
            order.save(update_fields=['status', 'completed_by', 'completed_at', 'updated_at'])
            return order

    @staticmethod
    @transaction.atomic
    def cancel_order(order, user):
        OrderService._validate_order_branch(order, user)

        if order.status in ['completed', 'cancelled']:
            raise ValidationError(f"Cannot cancel order in status: {order.status}")

        if order.is_custom_order and order.status == 'confirmed':
            OrderService._release_order_reservations(order, user)

        order.status = 'cancelled'
        order.cancelled_by = user
        order.cancelled_at = timezone.now()
        order.save(update_fields=['status', 'cancelled_by', 'cancelled_at', 'updated_at'])
        return order

    # =========================
    # PAYMENT MANAGEMENT
    # =========================
    @staticmethod
    def add_payment_to_order(order, amount, method, processed_by, reference=None, payment_type='payment', notes=''):
        return PaymentService.add_payment(
            order=order,
            amount=amount,
            method=method,
            processed_by=processed_by,
            reference=reference,
            payment_type=payment_type,
            notes=notes,
        )

    @staticmethod
    def refund_order(order, amount, reason, processed_by, reference=None):
        return PaymentService.process_refund(
            order=order,
            amount=amount,
            processed_by=processed_by,
            reference=reference,
            notes=reason,
        )

    @staticmethod
    def writeoff_order_balance(order, processed_by, reference=None, notes=''):
        return PaymentService.writeoff_order_balance(
            order=order,
            processed_by=processed_by,
            reference=reference,
            notes=notes,
        )

    # =========================
    # STOCK MANAGEMENT (PRIVATE METHODS)
    # =========================
    @staticmethod
    def _validate_order_branch(order, user):
        if not getattr(user, 'is_admin', False) and order.branch != getattr(user.profile, 'branch', None):
            raise ValidationError("Order does not belong to your branch")

    @staticmethod
    def _reserve_order_stock(order, user, ttl_hours=4):
        expires_at = timezone.now() + timedelta(hours=ttl_hours)
        for item in order.items.select_related('variant').all():
            if not item.variant:
                raise ValidationError("Order item has no variant to reserve")
            if item.quantity > item.variant.available_quantity:
                raise ValidationError(
                    f"Insufficient stock to reserve {item.product.name}. Available: {item.variant.available_quantity}, requested: {item.quantity}"
                )

            InventoryService.create_inventory_transaction(
                branch=order.branch,
                transaction_type='reservation',
                product=item.product,
                variant=item.variant,
                quantity_change=item.quantity,
                unit_cost=item.variant.cost_price,
                created_by=user,
                order=order,
                notes=f"Reserve stock for {order.order_number}"
            )

            StockReservation.objects.create(
                order=order,
                variant=item.variant,
                reserved_quantity=item.quantity,
                expires_at=expires_at,
                active=True,
            )

    @staticmethod
    def _release_order_reservations(order, user):
        reservations = order.stock_reservations.filter(active=True).select_related('variant')
        for reservation in reservations:
            InventoryService.create_inventory_transaction(
                branch=order.branch,
                transaction_type='reservation_release',
                product=reservation.variant.product,
                variant=reservation.variant,
                quantity_change=-reservation.reserved_quantity,
                unit_cost=reservation.variant.cost_price,
                created_by=user,
                order=order,
                notes=f"Release reservation for {order.order_number}"
            )
            reservation.active = False
            reservation.save(update_fields=['active'])

    @staticmethod
    def _recalculate_order_total(order):
        total = sum(item.subtotal for item in order.items.all())
        order.total_amount = total
        order.save(update_fields=['total_amount', 'updated_at'])


class PaymentService:
    @staticmethod
    @transaction.atomic
    def add_payment(order, amount, method, processed_by, reference=None, payment_type='payment', notes='', idempotency_key=None):
        if order.status in ['completed', 'cancelled']:
            raise ValidationError("Cannot add payments to completed or cancelled orders")

        if amount <= 0:
            raise ValidationError("Payment amount must be greater than zero")

        if not getattr(processed_by, 'is_admin', False) and order.branch != getattr(processed_by.profile, 'branch', None):
            raise ValidationError("Order does not belong to your branch")

        # Check for idempotency
        if idempotency_key:
            existing = Payment.objects.filter(order=order, idempotency_key=idempotency_key).first()
            if existing:
                return existing

        # Acquire distributed lock for order operations
        with get_order_lock(order.id):
            if reference:
                existing = Payment.objects.filter(reference=reference).first()
                if existing:
                    if existing.order_id != order.id:
                        raise ValidationError("Payment reference already used for a different order")
                    return existing

            remaining_due = order.discounted_total - order.amount_paid
            if payment_type == 'payment' and order.amount_paid + Decimal(amount) > order.discounted_total:
                payment_type = 'overpayment'

            payment = Payment.objects.create(
                order=order,
                amount=Decimal(amount),
                method=method,
                payment_type=payment_type,
                reference=reference or '',
                notes=notes,
                processed_by=processed_by,
                idempotency_key=idempotency_key,
            )

            cash_account = finance_services.get_standard_account(order.branch, '1000')
            ar_account = finance_services.get_standard_account(order.branch, '1100')
            deposit_account = finance_services.get_standard_account(order.branch, '1500')
            overpayment_account = finance_services.get_standard_account(order.branch, '1510')
            journal_entry = None

            if payment_type == 'deposit':
                journal_entry = finance_services.record_customer_deposit(
                    branch=order.branch,
                    created_by=processed_by,
                    amount=payment.amount,
                    reference=payment.reference or f"DEP-{order.order_number}-{payment.id}",
                    description=f"Customer deposit for order {order.order_number}",
                )
            elif payment_type in ['payment', 'overpayment']:
                amount_to_ar = min(payment.amount, max(Decimal('0.00'), remaining_due))
                excess = payment.amount - amount_to_ar
                lines = [
                    {'account': cash_account, 'line_type': 'debit', 'amount': payment.amount},
                ]
                if amount_to_ar > 0:
                    lines.append({'account': ar_account, 'line_type': 'credit', 'amount': amount_to_ar})
                if excess > 0:
                    lines.append({
                        'account': overpayment_account if payment_type == 'overpayment' else deposit_account,
                        'line_type': 'credit',
                        'amount': excess,
                    })
                journal_entry = finance_services.create_journal_entry(
                    branch=order.branch,
                    created_by=processed_by,
                    reference=payment.reference or f"PAY-{order.order_number}-{payment.id}",
                    description=f"Customer payment for order {order.order_number}",
                    entry_date=timezone.now().date(),
                    lines=lines,
                    source_document_type='OrderPayment',
                    source_document_id=str(payment.id),
                )
            elif payment_type == 'writeoff':
                journal_entry = finance_services.create_journal_entry(
                    branch=order.branch,
                    created_by=processed_by,
                    reference=payment.reference or f"WO-{order.order_number}-{payment.id}",
                    description=f"Write off balance for order {order.order_number}",
                    entry_date=timezone.now().date(),
                    lines=[
                        {'account': finance_services.get_standard_account(order.branch, '6000'), 'line_type': 'debit', 'amount': payment.amount},
                        {'account': ar_account, 'line_type': 'credit', 'amount': payment.amount},
                    ],
                    source_document_type='OrderPayment',
                    source_document_id=str(payment.id),
                )

            if journal_entry is not None:
                payment.journal_entry = journal_entry
                payment.save(update_fields=['journal_entry'])
            else:
                payment.save()

            order.recalculate_payment_status()
            return payment

    @staticmethod
    @transaction.atomic
    def process_refund(order, amount, processed_by, reference=None, notes=''):
        if order.status != 'completed':
            raise ValidationError("Can only refund completed orders")

        if amount <= 0:
            raise ValidationError("Refund amount must be greater than zero")

        if not getattr(processed_by, 'is_admin', False) and order.branch != getattr(processed_by.profile, 'branch', None):
            raise ValidationError("Order does not belong to your branch")

        if reference:
            existing = Payment.objects.filter(reference=reference, order=order, payment_type='refund').first()
            if existing:
                return existing

        if amount > order.amount_paid:
            raise ValidationError("Cannot refund more than the amount paid")

        refund = Payment.objects.create(
            order=order,
            amount=-Decimal(amount),
            method='cash',
            payment_type='refund',
            reference=reference or '',
            notes=notes,
            processed_by=processed_by,
        )

        journal_entry = finance_services.record_refund(
            branch=order.branch,
            created_by=processed_by,
            amount=Decimal(amount),
            reference=refund.reference or f"REF-{order.order_number}-{refund.id}",
            description=f"Refund for order {order.order_number}",
        )
        refund.journal_entry = journal_entry
        refund.save(update_fields=['journal_entry'])

        order.recalculate_payment_status()
        return refund

    @staticmethod
    @transaction.atomic
    def reverse_payment(order, reference, processed_by, notes=''):
        payment = Payment.objects.filter(reference=reference, order=order).first()
        if not payment:
            raise ValidationError("Payment reference not found")

        if payment.payment_type == 'refund':
            raise ValidationError("Cannot reverse a refund payment")

        reversal = Payment.objects.create(
            order=order,
            amount=-payment.amount,
            method=payment.method,
            payment_type='reversal',
            reference=f"REV-{reference}",
            notes=notes,
            processed_by=processed_by,
        )

        amount = abs(payment.amount)
        cash = finance_services.get_standard_account(order.branch, '1000')
        ar = finance_services.get_standard_account(order.branch, '1100')
        journal_entry = finance_services.create_journal_entry(
            branch=order.branch,
            created_by=processed_by,
            reference=reversal.reference,
            description=f"Payment reversal for order {order.order_number}",
            entry_date=timezone.now().date(),
            lines=[
                {'account': ar, 'line_type': 'debit', 'amount': amount},
                {'account': cash, 'line_type': 'credit', 'amount': amount},
            ],
            source_document_type='OrderPayment',
            source_document_id=str(reversal.id),
        )
        reversal.journal_entry = journal_entry
        reversal.save(update_fields=['journal_entry'])

        order.recalculate_payment_status()
        return reversal

    @staticmethod
    @transaction.atomic
    def writeoff_order_balance(order, processed_by, reference=None, notes=''):
        if order.balance_due <= 0:
            raise ValidationError("No outstanding balance to write off")

        if not getattr(processed_by, 'is_admin', False) and order.branch != getattr(processed_by.profile, 'branch', None):
            raise ValidationError("Order does not belong to your branch")

        payment = Payment.objects.create(
            order=order,
            amount=order.balance_due,
            method='adjustment',
            payment_type='writeoff',
            reference=reference or '',
            notes=notes,
            processed_by=processed_by,
        )

        amount = payment.amount
        expense_account = finance_services.get_standard_account(order.branch, '6000')
        ar_account = finance_services.get_standard_account(order.branch, '1100')
        journal_entry = finance_services.create_journal_entry(
            branch=order.branch,
            created_by=processed_by,
            reference=payment.reference or f"WO-{order.order_number}-{payment.id}",
            description=f"Write-off for order {order.order_number}",
            entry_date=timezone.now().date(),
            lines=[
                {'account': expense_account, 'line_type': 'debit', 'amount': amount},
                {'account': ar_account, 'line_type': 'credit', 'amount': amount},
            ],
            source_document_type='OrderPayment',
            source_document_id=str(payment.id),
        )
        payment.journal_entry = journal_entry
        payment.save(update_fields=['journal_entry'])

        order.recalculate_payment_status()
        return payment
