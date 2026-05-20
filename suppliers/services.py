"""
SupplierService: Production-grade service layer for Supplier business logic.
Handles all transactional operations with proper state management and concurrency control.
"""

from django.db import transaction
from django.db.models import Sum
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from .models import Supplier, Purchase, PurchaseItem, PurchasePayment
from inventory.models import InventoryTransaction
from inventory.services import InventoryService
from finance import services as finance_services
from common.locking import get_purchase_lock


class SupplierService:
    """
    Centralized service layer for all Supplier business logic.
    Handles transactions, state management, and inventory integration.
    """

    # =========================
    # PURCHASE PAYMENT PROCESSING
    # =========================
    @staticmethod
    @transaction.atomic
    def record_purchase_payment(purchase, amount, processed_by, reference=None, notes='', idempotency_key=None):
        """
        Record payment for a purchase order with proper validation and audit trail.
        """
        if purchase.status not in ['ordered', 'partially_received', 'received']:
            raise ValidationError("Cannot record payment for purchase in current status")

        if amount <= 0:
            raise ValidationError("Payment amount must be greater than zero")

        if not getattr(processed_by, 'is_admin', False) and purchase.branch != getattr(processed_by.profile, 'branch', None):
            raise ValidationError("Purchase does not belong to your branch")

        # Check for idempotency
        if idempotency_key:
            existing = PurchasePayment.objects.filter(purchase=purchase, idempotency_key=idempotency_key).first()
            if existing:
                return purchase, existing

        # Acquire distributed lock for purchase operations
        with get_purchase_lock(purchase.id):
            if reference:
                existing_payment = PurchasePayment.objects.filter(
                    branch=purchase.branch,
                    reference=reference
                ).exclude(purchase=purchase).first()
                if existing_payment is not None:
                    raise ValidationError("Payment reference already used for a different purchase")

            purchase = Purchase.objects.select_for_update().get(pk=purchase.pk)
            new_paid = purchase.amount_paid + Decimal(amount)
            if new_paid > purchase.total_amount:
                raise ValidationError("Payment amount exceeds outstanding balance")

            purchase.amount_paid = new_paid
            if new_paid >= purchase.total_amount:
                purchase.payment_status = 'paid'
            else:
                purchase.payment_status = 'partial'

            payment_record = PurchasePayment.objects.create(
                purchase=purchase,
                branch=purchase.branch,
                amount=Decimal(amount),
                payment_type='payment',
                processed_by=processed_by,
                reference=reference or '',
                notes=notes,
                idempotency_key=idempotency_key,
                method='cash',
            )

            purchase.save(update_fields=['amount_paid', 'payment_status', 'updated_at'])

            journal_entry = finance_services.record_supplier_payment(
                branch=purchase.branch,
                created_by=processed_by,
                amount=payment_record.amount,
                reference=payment_record.reference or f"SUPPAY-{purchase.purchase_number}-{payment_record.id}",
                description=f"Supplier payment for purchase {purchase.purchase_number}",
            )

            payment_record.journal_entry = journal_entry
            payment_record.save(update_fields=['journal_entry'])

            return purchase, payment_record

    # =========================
    # PURCHASE RECEIVING
    # =========================
    @staticmethod
    @transaction.atomic
    def process_purchase_receipt(purchase, received_items, processed_by):
        """
        Process receipt of purchase order items with inventory integration.
        """
        if purchase.status == 'cancelled':
            raise ValidationError("Cannot receive items for cancelled purchase")

        if not getattr(processed_by, 'is_admin', False) and purchase.branch != getattr(processed_by.profile, 'branch', None):
            raise ValidationError("Purchase does not belong to your branch")

        # Validate received items
        for item_data in received_items:
            purchase_item = item_data['purchase_item']
            received_quantity = item_data['received_quantity']

            if received_quantity < 0:
                raise ValidationError("Received quantity cannot be negative")

            if received_quantity > purchase_item.quantity:
                raise ValidationError(f"Cannot receive more than ordered for {purchase_item.product.name}")

        # Process inventory transactions
        transactions = InventoryService.process_purchase_receipt(purchase, received_items, processed_by)

        # Update purchase status
        total_received = sum(t.quantity_change for t in transactions)
        total_ordered = sum(item.quantity for item in purchase.items.all())

        if total_received >= total_ordered:
            purchase.status = 'received'
        else:
            purchase.status = 'partially_received'

        purchase.save(update_fields=['status', 'updated_at'])

        received_value = sum(
            item_data['received_quantity'] * item_data['purchase_item'].unit_price
            for item_data in received_items
        )
        total_received = InventoryTransaction.objects.filter(
            purchase=purchase,
            transaction_type='purchase_receipt'
        ).aggregate(total=Sum('quantity_change'))['total'] or 0
        total_ordered = sum(item.quantity for item in purchase.items.all())

        if total_received >= total_ordered:
            purchase.status = 'received'
        else:
            purchase.status = 'partially_received'

        purchase.save(update_fields=['status', 'updated_at'])

        return purchase, transactions