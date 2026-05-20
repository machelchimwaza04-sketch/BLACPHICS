"""
InventoryService: Production-grade business logic for inventory operations.

Handles:
- Stock level management with concurrency control
- Inventory transaction processing
- Double-entry ledger accounting
- Stock adjustments and approvals
- Inventory valuation and reconciliation
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal
from .models import (
    InventoryTransaction, InventoryLedger, InventoryCostLayer, StockAdjustment,
    InventorySnapshot, InventorySnapshotItem
)
from products.models import Product, ProductVariant
from finance import services as finance_services
from common.locking import get_inventory_lock


class InventoryService:
    """
    Centralized service for all inventory operations.
    Ensures atomicity, consistency, and proper audit trails.
    """

    @staticmethod
    def _assert_branch_matches(branch, product, variant=None):
        if product.branch != branch:
            raise ValidationError("Product does not belong to the requested branch")
        if variant and variant.product.branch != branch:
            raise ValidationError("Variant does not belong to the requested branch")

    @staticmethod
    def _apply_stock_change(transaction_obj):
        if transaction_obj.variant:
            variant = ProductVariant.objects.select_for_update().get(pk=transaction_obj.variant.pk)

            if transaction_obj.transaction_type == 'reservation':
                if transaction_obj.quantity_change <= 0:
                    raise ValidationError("Reservation quantity must be positive")
                if variant.available_quantity < transaction_obj.quantity_change:
                    raise ValidationError(
                        f"Insufficient available stock for {variant}. Available: {variant.available_quantity}"
                    )
                variant.committed_quantity += transaction_obj.quantity_change
                variant.save(update_fields=['committed_quantity'])
                return variant

            if transaction_obj.transaction_type == 'reservation_release':
                release_quantity = abs(transaction_obj.quantity_change)
                if variant.committed_quantity < release_quantity:
                    raise ValidationError(
                        f"Cannot release more reserved stock than committed for {variant}"
                    )
                variant.committed_quantity -= release_quantity
                variant.save(update_fields=['committed_quantity'])
                return variant

            new_quantity = variant.stock_quantity + transaction_obj.quantity_change
            if new_quantity < 0:
                raise ValidationError(f"Insufficient stock for {variant}. Available: {variant.stock_quantity}")
            variant.stock_quantity = new_quantity
            variant.save(update_fields=['stock_quantity'])
            return variant

        product = Product.objects.select_for_update().get(pk=transaction_obj.product.pk)
        new_quantity = product.stock_quantity + transaction_obj.quantity_change
        if new_quantity < 0:
            raise ValidationError(f"Insufficient stock for {product}. Available: {product.stock_quantity}")
        product.stock_quantity = new_quantity
        product.save(update_fields=['stock_quantity'])
        return product

    @staticmethod
    @transaction.atomic
    def create_inventory_transaction(
        branch, transaction_type, product, variant=None,
        quantity_change=0, unit_cost=Decimal('0.00'), unit_price=Decimal('0.00'),
        created_by=None, order=None, purchase=None, adjustment=None, notes='',
        idempotency_key=None
    ):
        InventoryService._assert_branch_matches(branch, product, variant)

        if transaction_type in ['sale', 'transfer_out', 'damage', 'reservation_release'] and quantity_change >= 0:
            raise ValidationError(f"{transaction_type} transactions must reduce stock or reservations")
        if transaction_type in ['purchase_receipt', 'transfer_in', 'return', 'reservation'] and quantity_change <= 0:
            raise ValidationError(f"{transaction_type} transactions must increase stock or reservations")

        # Check for idempotency
        if idempotency_key:
            existing = InventoryTransaction.objects.filter(
                branch=branch,
                idempotency_key=idempotency_key
            ).first()
            if existing:
                return existing

        # Acquire distributed lock for inventory operations
        with get_inventory_lock(branch.id, product.id, variant.id if variant else None):
            transaction_obj = InventoryTransaction.objects.create(
                branch=branch,
                transaction_type=transaction_type,
                product=product,
                variant=variant,
                order=order,
                purchase=purchase,
                adjustment=adjustment,
                quantity_change=quantity_change,
                unit_cost=unit_cost,
                unit_price=unit_price,
                notes=notes,
                created_by=created_by,
                idempotency_key=idempotency_key,
                status='completed',
                completed_at=timezone.now(),
                completed_by=created_by
            )

            InventoryService._apply_stock_change(transaction_obj)

            if transaction_type in ['sale', 'transfer_out', 'damage', 'count'] and quantity_change < 0:
                transaction_obj.unit_cost = InventoryService._consume_fifo_cost_layers(
                    branch=branch,
                    product=product,
                    variant=variant,
                    quantity=abs(quantity_change)
                )
                transaction_obj.save(update_fields=['unit_cost'])

            if transaction_type in ['purchase_receipt', 'return', 'transfer_in', 'adjustment', 'count'] and quantity_change > 0:
                InventoryService._create_cost_layer(transaction_obj)

            InventoryService._create_ledger_entries(transaction_obj)
            return transaction_obj

    @staticmethod
    def _create_cost_layer(transaction_obj):
        InventoryCostLayer.objects.create(
            branch=transaction_obj.branch,
            product=transaction_obj.product,
            variant=transaction_obj.variant,
            remaining_quantity=abs(transaction_obj.quantity_change),
            unit_cost=transaction_obj.unit_cost,
            source_transaction=transaction_obj,
        )

    @staticmethod
    def _consume_fifo_cost_layers(branch, product, variant, quantity):
        remaining = quantity
        total_cost = Decimal('0.00')
        cost_layers = InventoryCostLayer.objects.select_for_update().filter(
            branch=branch,
            product=product,
            variant=variant,
            remaining_quantity__gt=0
        ).order_by('created_at')

        available = cost_layers.aggregate(total=Sum('remaining_quantity'))['total'] or 0
        if available < remaining:
            raise ValidationError('Insufficient inventory cost layers available for sale.')

        for layer in cost_layers:
            if remaining <= 0:
                break
            consumed = min(layer.remaining_quantity, remaining)
            layer.remaining_quantity -= consumed
            layer.save(update_fields=['remaining_quantity'])
            total_cost += consumed * layer.unit_cost
            remaining -= consumed

        if remaining > 0:
            raise ValidationError('Insufficient inventory cost layers available for sale.')

        return (total_cost / Decimal(quantity)).quantize(Decimal('0.01'))

    @staticmethod
    def _create_ledger_entries(transaction_obj):
        entries = []

        if transaction_obj.transaction_type == 'purchase_receipt':
            entries.append(InventoryLedger(
                branch=transaction_obj.branch,
                transaction=transaction_obj,
                entry_type='debit',
                account_type='inventory_asset',
                amount=transaction_obj.total_cost_value,
                product=transaction_obj.product,
                variant=transaction_obj.variant
            ))

        elif transaction_obj.transaction_type == 'sale':
            entries.extend([
                InventoryLedger(
                    branch=transaction_obj.branch,
                    transaction=transaction_obj,
                    entry_type='debit',
                    account_type='cogs_expense',
                    amount=transaction_obj.total_cost_value,
                    product=transaction_obj.product,
                    variant=transaction_obj.variant
                ),
                InventoryLedger(
                    branch=transaction_obj.branch,
                    transaction=transaction_obj,
                    entry_type='credit',
                    account_type='inventory_asset',
                    amount=transaction_obj.total_cost_value,
                    product=transaction_obj.product,
                    variant=transaction_obj.variant
                )
            ])

        elif transaction_obj.transaction_type == 'return':
            entries.extend([
                InventoryLedger(
                    branch=transaction_obj.branch,
                    transaction=transaction_obj,
                    entry_type='debit',
                    account_type='inventory_asset',
                    amount=transaction_obj.total_cost_value,
                    product=transaction_obj.product,
                    variant=transaction_obj.variant
                ),
                InventoryLedger(
                    branch=transaction_obj.branch,
                    transaction=transaction_obj,
                    entry_type='credit',
                    account_type='cogs_expense',
                    amount=transaction_obj.total_cost_value,
                    product=transaction_obj.product,
                    variant=transaction_obj.variant
                )
            ])

        elif transaction_obj.transaction_type in ['adjustment', 'count', 'damage']:
            amount = abs(transaction_obj.total_cost_value)
            entry_type = 'debit' if transaction_obj.quantity_change > 0 else 'credit'
            entries.append(InventoryLedger(
                branch=transaction_obj.branch,
                transaction=transaction_obj,
                entry_type=entry_type,
                account_type='inventory_adjustment',
                amount=amount,
                product=transaction_obj.product,
                variant=transaction_obj.variant
            ))

        elif transaction_obj.transaction_type in ['transfer_out', 'transfer_in']:
            amount = abs(transaction_obj.total_cost_value)
            entry_type = 'credit' if transaction_obj.transaction_type == 'transfer_out' else 'debit'
            entries.append(InventoryLedger(
                branch=transaction_obj.branch,
                transaction=transaction_obj,
                entry_type=entry_type,
                account_type='inventory_asset',
                amount=amount,
                product=transaction_obj.product,
                variant=transaction_obj.variant
            ))

        if entries:
            InventoryLedger.objects.bulk_create(entries)

        inventory_gl = InventoryService._create_general_ledger_entry(transaction_obj)
        if inventory_gl is not None:
            transaction_obj.general_ledger_entry = inventory_gl
            transaction_obj.save(update_fields=['general_ledger_entry'])

    # =========================
    @staticmethod
    def _create_general_ledger_entry(transaction_obj):
        if transaction_obj.transaction_type in ['reservation', 'reservation_release']:
            return None

        branch = transaction_obj.branch
        created_by = transaction_obj.created_by
        reference = transaction_obj.transaction_number
        description = f"Inventory {transaction_obj.transaction_type.replace('_', ' ')} for {transaction_obj.transaction_number}"
        movement = transaction_obj.total_cost_value

        inventory_asset = finance_services.get_standard_account(branch, '1200')
        accounts_payable = finance_services.get_standard_account(branch, '2000')
        cogs = finance_services.get_standard_account(branch, '5000')
        inventory_adjustment = finance_services.get_standard_account(branch, '5200')

        lines = []
        if transaction_obj.transaction_type == 'purchase_receipt':
            lines = [
                {'account': inventory_asset, 'line_type': 'debit', 'amount': movement},
                {'account': accounts_payable, 'line_type': 'credit', 'amount': movement},
            ]
        elif transaction_obj.transaction_type == 'sale':
            lines = [
                {'account': cogs, 'line_type': 'debit', 'amount': movement},
                {'account': inventory_asset, 'line_type': 'credit', 'amount': movement},
            ]
        elif transaction_obj.transaction_type == 'return':
            lines = [
                {'account': inventory_asset, 'line_type': 'debit', 'amount': movement},
                {'account': cogs, 'line_type': 'credit', 'amount': movement},
            ]
        elif transaction_obj.transaction_type in ['adjustment', 'damage', 'count']:
            if transaction_obj.quantity_change > 0:
                lines = [
                    {'account': inventory_asset, 'line_type': 'debit', 'amount': movement},
                    {'account': inventory_adjustment, 'line_type': 'credit', 'amount': movement},
                ]
            else:
                lines = [
                    {'account': inventory_adjustment, 'line_type': 'debit', 'amount': movement},
                    {'account': inventory_asset, 'line_type': 'credit', 'amount': movement},
                ]
        elif transaction_obj.transaction_type in ['transfer_in', 'transfer_out']:
            return None

        if not lines:
            return None

        return finance_services.create_journal_entry(
            branch=branch,
            created_by=created_by,
            reference=reference,
            description=description,
            entry_date=transaction_obj.completed_at.date() if transaction_obj.completed_at else timezone.now().date(),
            lines=lines,
        )

    # =========================
    # STOCK ADJUSTMENTS
    # =========================
    @staticmethod
    @transaction.atomic
    def create_stock_adjustment(
        branch, adjustment_type, product, variant=None,
        system_quantity=0, actual_quantity=0, unit_cost=Decimal('0.00'),
        created_by=None, reason='', notes='', related_purchase=None
    ):
        """
        Create a stock adjustment with approval workflow.
        """
        adjustment_quantity = actual_quantity - system_quantity

        adjustment = StockAdjustment.objects.create(
            branch=branch,
            adjustment_type=adjustment_type,
            product=product,
            variant=variant,
            system_quantity=system_quantity,
            actual_quantity=actual_quantity,
            adjustment_quantity=adjustment_quantity,
            unit_cost=unit_cost,
            total_value_impact=adjustment_quantity * unit_cost,
            reason=reason,
            notes=notes,
            related_purchase=related_purchase,
            created_by=created_by,
            status='draft'
        )

        # Auto-approve if no approval required
        if not adjustment.requires_approval:
            adjustment.status = 'approved'
            adjustment.approved_by = created_by
            adjustment.approved_at = timezone.now()
            adjustment.save()

        return adjustment

    @staticmethod
    @transaction.atomic
    def process_stock_adjustment(adjustment, user):
        """
        Process an approved stock adjustment into inventory transaction.
        """
        if adjustment.status != 'approved':
            raise ValidationError("Only approved adjustments can be processed")

        # Create inventory transaction
        transaction_obj = InventoryService.create_inventory_transaction(
            branch=adjustment.branch,
            transaction_type='adjustment',
            product=adjustment.product,
            variant=adjustment.variant,
            quantity_change=adjustment.adjustment_quantity,
            unit_cost=adjustment.unit_cost,
            created_by=user,
            adjustment=adjustment,
            notes=f"Adjustment: {adjustment.reason}"
        )

        # Mark adjustment as completed
        adjustment.completed_by = user
        adjustment.completed_at = timezone.now()
        adjustment.status = 'completed'
        adjustment.save()

        return transaction_obj

    # =========================
    # PURCHASE RECEIPT PROCESSING
    # =========================
    @staticmethod
    @transaction.atomic
    def process_purchase_receipt(purchase, received_items, user):
        """
        Process receipt of purchase order items.
        """
        transactions = []

        for item_data in received_items:
            purchase_item = item_data['purchase_item']
            received_quantity = item_data['received_quantity']
            unit_cost = purchase_item.unit_price

            transaction_obj = InventoryService.create_inventory_transaction(
                branch=purchase.branch,
                transaction_type='purchase_receipt',
                product=purchase_item.product,
                variant=getattr(purchase_item, 'variant', None),
                quantity_change=received_quantity,
                unit_cost=unit_cost,
                created_by=user,
                purchase=purchase,
                notes=f"Purchase receipt: {purchase.purchase_number}"
            )

            transactions.append(transaction_obj)

        # Update purchase status
        total_received = sum(t.quantity_change for t in transactions)
        total_ordered = sum(item.quantity for item in purchase.items.all())

        if total_received >= total_ordered:
            purchase.status = 'received'
        else:
            purchase.status = 'partially_received'

        purchase.save()

        return transactions

    # =========================
    # ORDER PROCESSING INTEGRATION
    # =========================
    @staticmethod
    @transaction.atomic
    def process_order_completion(order, user):
        """
        Process inventory transactions when an order is completed.
        """
        transactions = []

        for item in order.items.select_related('variant').all():
            unit_cost = item.variant.cost_price if item.variant else Decimal('0.00')
            transaction_obj = InventoryService.create_inventory_transaction(
                branch=order.branch,
                transaction_type='sale',
                product=item.product,
                variant=item.variant,
                quantity_change=-item.quantity,
                unit_cost=unit_cost,
                unit_price=item.final_unit_price or item.unit_price,
                created_by=user,
                order=order,
                notes=f"Order completion: {order.order_number}"
            )

            transactions.append(transaction_obj)

        return transactions

    # =========================
    # RECONCILIATION
    # =========================
    @staticmethod
    def get_committed_reconciliation(branch):
        variants = ProductVariant.objects.filter(product__branch=branch).prefetch_related('product')
        reconciliation = []

        for variant in variants:
            reserved_total = InventoryTransaction.objects.filter(
                branch=branch,
                variant=variant,
                transaction_type__in=['reservation', 'reservation_release']
            ).aggregate(total=Sum('quantity_change'))['total'] or 0

            expected_committed = max(0, reserved_total)
            if variant.committed_quantity != expected_committed:
                reconciliation.append({
                    'variant_id': variant.id,
                    'variant': str(variant),
                    'committed_quantity': variant.committed_quantity,
                    'expected_committed_quantity': expected_committed,
                    'variance': variant.committed_quantity - expected_committed,
                })

        return reconciliation

    # =========================
    # INVENTORY SNAPSHOTS & RECONCILIATION
    # =========================
    @staticmethod
    @transaction.atomic
    def create_inventory_snapshot(branch, snapshot_type, created_by, physical_counts=None):
        """
        Create inventory snapshot for reconciliation.
        """
        # Get all products and variants for this branch
        products = Product.objects.filter(branch=branch).prefetch_related('variants')
        physical_counts = physical_counts or {}

        total_products = 0
        total_variants = 0
        total_units = 0
        total_value = Decimal('0.00')
        low_stock_count = 0
        out_of_stock_count = 0

        snapshot_items = []

        for product in products:
            total_products += 1

            # Product-level stock
            if product.stock_quantity > 0:
                total_units += product.stock_quantity
                # Would need cost_price on Product model
                product_value = Decimal('0.00')  # Placeholder
                total_value += product_value

                if product.is_low_stock:
                    low_stock_count += 1
                if product.stock_quantity == 0:
                    out_of_stock_count += 1

                # Create snapshot item
                physical_qty = physical_counts.get(f"product_{product.id}")
                snapshot_items.append(InventorySnapshotItem(
                    product=product,
                    system_quantity=product.stock_quantity,
                    physical_quantity=physical_qty,
                    unit_cost=Decimal('0.00'),  # Placeholder
                    total_value=product_value,
                    variance_quantity=physical_qty - product.stock_quantity if physical_qty else None
                ))

            # Variant-level stock
            for variant in product.variants.all():
                total_variants += 1
                if variant.stock_quantity > 0:
                    total_units += variant.stock_quantity
                    variant_value = variant.stock_quantity * variant.cost_price
                    total_value += variant_value

                    if variant.stock_status == 'low_stock':
                        low_stock_count += 1
                    if variant.stock_status == 'out_of_stock':
                        out_of_stock_count += 1

                    # Create snapshot item
                    physical_qty = physical_counts.get(f"variant_{variant.id}")
                    snapshot_items.append(InventorySnapshotItem(
                        product=product,
                        variant=variant,
                        system_quantity=variant.stock_quantity,
                        physical_quantity=physical_qty,
                        unit_cost=variant.cost_price,
                        total_value=variant_value,
                        variance_quantity=physical_qty - variant.stock_quantity if physical_qty else None,
                        variance_value=(physical_qty - variant.stock_quantity) * variant.cost_price if physical_qty else None
                    ))

        # Create snapshot
        snapshot = InventorySnapshot.objects.create(
            branch=branch,
            snapshot_type=snapshot_type,
            total_products=total_products,
            total_variants=total_variants,
            total_units=total_units,
            total_value=total_value,
            low_stock_count=low_stock_count,
            out_of_stock_count=out_of_stock_count,
            created_by=created_by
        )

        # Bulk create snapshot items
        for item in snapshot_items:
            item.snapshot = snapshot
        InventorySnapshotItem.objects.bulk_create(snapshot_items)

        return snapshot

    # =========================
    # REPORTING & ANALYTICS
    # =========================
    @staticmethod
    def get_inventory_valuation(branch, valuation_method='fifo'):
        """
        Calculate inventory valuation using physical stock counts and reconcile against GL inventory asset balance.

        The GL inventory asset account is the authoritative valuation, while physical valuation
        assists reconciliation and identifies stock cost variances.
        """
        products = Product.objects.filter(branch=branch).prefetch_related('variants')

        physical_value = Decimal('0.00')
        cost_layers = InventoryCostLayer.objects.filter(branch=branch)
        for layer in cost_layers:
            physical_value += layer.remaining_quantity * layer.unit_cost

        gl_inventory_value = finance_services.get_account_balance(branch, '1200')

        return {
            'physical_value': physical_value,
            'total_value': physical_value,
            'ledger_inventory_value': gl_inventory_value,
            'variance': gl_inventory_value - physical_value,
            'valuation_method': valuation_method,
            'calculated_at': timezone.now()
        }

    @staticmethod
    def get_inventory_turnover(branch, period_days=30):
        """
        Calculate inventory turnover ratio.
        """
        from django.db.models import Sum
        from django.utils import timezone
        from datetime import timedelta

        end_date = timezone.now()
        start_date = end_date - timedelta(days=period_days)

        # COGS for period
        cogs_entries = InventoryLedger.objects.filter(
            branch=branch,
            account_type='cogs_expense',
            created_at__range=(start_date, end_date)
        ).aggregate(total_cogs=Sum('amount'))

        # Average inventory value
        avg_inventory = InventoryService.get_inventory_valuation(branch)['physical_value']

        cogs = cogs_entries['total_cogs'] or Decimal('0.00')

        if avg_inventory > 0:
            turnover_ratio = (cogs / avg_inventory) * (365 / period_days)
        else:
            turnover_ratio = Decimal('0.00')

        return {
            'cogs': cogs,
            'average_inventory': avg_inventory,
            'turnover_ratio': turnover_ratio,
            'period_days': period_days
        }