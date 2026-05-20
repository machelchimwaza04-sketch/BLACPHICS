# finance/reconciliation.py
"""
Enterprise Reconciliation Service

Automated integrity verification for financial systems.
Detects discrepancies between operational records and general ledger.
"""

from django.db import transaction
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
from .models import Account, JournalEntry, JournalLine, ReconciliationRun
from .services import get_account_balance, get_standard_account
from orders.models import Order, Payment
from suppliers.models import Purchase, PurchasePayment
from inventory.models import InventoryTransaction
from inventory.services import InventoryService
from branches.models import Branch


class ReconciliationService:
    """
    Enterprise-grade reconciliation engine for financial integrity.
    """

    @staticmethod
    def reconcile_ar_balance(branch=None, as_of_date=None):
        """
        Reconcile Accounts Receivable: GL vs Order balances
        """
        as_of_date = as_of_date or date.today()

        # GL AR balance
        gl_ar_balance = get_account_balance(branch, '1100', end_date=as_of_date)

        # Operational AR balance from completed orders
        orders_query = Order.objects.filter(status='completed')
        if branch:
            orders_query = orders_query.filter(branch=branch)

        operational_ar = Decimal('0.00')
        for order in orders_query:
            operational_ar += max(Decimal('0.00'), order.balance_due)

        variance = gl_ar_balance - operational_ar

        return {
            'gl_balance': gl_ar_balance,
            'operational_balance': operational_ar,
            'variance': variance,
            'is_reconciled': abs(variance) < Decimal('0.01'),
            'severity': 'CRITICAL' if abs(variance) >= Decimal('1.00') else 'WARNING' if abs(variance) >= Decimal('0.01') else 'OK',
            'details': {
                'completed_orders_count': orders_query.count(),
                'total_order_value': sum(order.discounted_total for order in orders_query),
                'total_paid': sum(order.amount_paid for order in orders_query),
            }
        }

    @staticmethod
    def reconcile_ap_balance(branch=None, as_of_date=None):
        """
        Reconcile Accounts Payable: GL vs Purchase balances
        """
        as_of_date = as_of_date or date.today()

        # GL AP balance
        gl_ap_balance = get_account_balance(branch, '2000', end_date=as_of_date)

        # Operational AP balance from unpaid purchases
        purchases_query = Purchase.objects.exclude(payment_status='paid')
        if branch:
            purchases_query = purchases_query.filter(branch=branch)

        operational_ap = Decimal('0.00')
        for purchase in purchases_query:
            operational_ap += max(Decimal('0.00'), purchase.balance_due)

        variance = gl_ap_balance - operational_ap

        return {
            'gl_balance': gl_ap_balance,
            'operational_balance': operational_ap,
            'variance': variance,
            'is_reconciled': abs(variance) < Decimal('0.01'),
            'severity': 'CRITICAL' if abs(variance) >= Decimal('1.00') else 'WARNING' if abs(variance) >= Decimal('0.01') else 'OK',
            'details': {
                'unpaid_purchases_count': purchases_query.count(),
                'total_purchase_value': sum(purchase.total_amount for purchase in purchases_query),
                'total_paid': sum(purchase.amount_paid for purchase in purchases_query),
            }
        }

    @staticmethod
    def reconcile_cash_balance(branch=None, as_of_date=None):
        """
        Reconcile Cash: GL vs Payment records
        """
        as_of_date = as_of_date or date.today()

        # GL cash balance
        gl_cash_balance = get_account_balance(branch, '1000', end_date=as_of_date)

        # Operational cash from payments
        payments_query = Payment.objects.all()
        if branch:
            payments_query = payments_query.filter(order__branch=branch)

        cash_in = payments_query.filter(amount__gt=0).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        cash_out = abs(payments_query.filter(amount__lt=0).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'))

        operational_cash = cash_in - cash_out

        # Supplier payments
        supplier_payments_query = PurchasePayment.objects.all()
        if branch:
            supplier_payments_query = supplier_payments_query.filter(branch=branch)

        supplier_cash_out = supplier_payments_query.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        operational_cash -= supplier_cash_out

        variance = gl_cash_balance - operational_cash

        return {
            'gl_balance': gl_cash_balance,
            'operational_balance': operational_cash,
            'variance': variance,
            'is_reconciled': abs(variance) < Decimal('0.01'),
            'severity': 'CRITICAL' if abs(variance) >= Decimal('1.00') else 'WARNING' if abs(variance) >= Decimal('0.01') else 'OK',
            'details': {
                'customer_payments_count': payments_query.count(),
                'supplier_payments_count': supplier_payments_query.count(),
                'total_cash_in': cash_in,
                'total_cash_out': cash_out + supplier_cash_out,
            }
        }

    @staticmethod
    def reconcile_inventory_valuation(branch=None, as_of_date=None):
        """
        Reconcile Inventory Asset: GL vs calculated stock valuation
        """
        as_of_date = as_of_date or date.today()

        # GL inventory balance
        gl_inventory_balance = get_account_balance(branch, '1200', end_date=as_of_date)

        # Operational inventory valuation via inventory service
        physical_inventory = InventoryService.get_inventory_valuation(branch)
        operational_valuation = physical_inventory.get('physical_value', Decimal('0.00'))

        variance = gl_inventory_balance - operational_valuation

        return {
            'gl_balance': gl_inventory_balance,
            'operational_balance': operational_valuation,
            'variance': variance,
            'is_reconciled': abs(variance) < Decimal('0.01'),
            'severity': 'CRITICAL' if abs(variance) >= Decimal('10.00') else 'WARNING' if abs(variance) >= Decimal('1.00') else 'OK',
            'details': {
                'variants_count': variants_query.count(),
                'products_count': products_query.count(),
                'total_units': sum(v.stock_quantity for v in variants_query) + sum(p.stock_quantity for p in products_query),
            }
        }

    @staticmethod
    def find_unbalanced_entries(branch=None):
        """
        Find journal entries that are not balanced
        """
        entries = JournalEntry.objects.filter(status='posted')
        if branch:
            entries = entries.filter(branch=branch)

        unbalanced = []
        for entry in entries:
            if not entry.is_balanced:
                unbalanced.append({
                    'entry_id': entry.id,
                    'reference': entry.reference,
                    'entry_date': entry.entry_date,
                    'description': entry.description,
                    'total_debits': entry.debit_total,
                    'total_credits': entry.credit_total,
                    'variance': entry.debit_total - entry.credit_total,
                })

        return {
            'unbalanced_count': len(unbalanced),
            'entries': unbalanced,
            'severity': 'CRITICAL' if len(unbalanced) > 0 else 'OK',
        }

    @staticmethod
    def find_orphaned_journal_lines():
        """
        Find journal lines not attached to entries
        """
        orphaned = JournalLine.objects.filter(entry__isnull=True)
        return {
            'orphaned_count': orphaned.count(),
            'lines': list(orphaned.values('id', 'account__code', 'amount', 'line_type')),
            'severity': 'CRITICAL' if orphaned.count() > 0 else 'OK',
        }

    @staticmethod
    def find_duplicate_references(branch=None):
        """
        Find duplicate journal entry references
        """
        entries = JournalEntry.objects.filter(status='posted')
        if branch:
            entries = entries.filter(branch=branch)

        duplicates = []
        duplicate_groups = (
            entries.values('reference')
            .annotate(count=Count('id'))
            .filter(count__gt=1)
        )

        for group in duplicate_groups:
            reference = group['reference']
            duplicate_entries = entries.filter(reference=reference)
            duplicates.append({
                'reference': reference,
                'entry_ids': list(duplicate_entries.values_list('id', flat=True)),
                'count': group['count'],
            })

        return {
            'duplicate_references': duplicates,
            'severity': 'WARNING' if len(duplicates) > 0 else 'OK',
        }

    @staticmethod
    def find_missing_source_links(branch=None):
        """
        Find journal entries without source document links
        """
        entries = JournalEntry.objects.filter(status='posted').filter(
            Q(source_document_type='') | Q(source_document_id='')
        )
        if branch:
            entries = entries.filter(branch=branch)

        return {
            'missing_links_count': entries.count(),
            'entries': list(entries.values('id', 'reference', 'description', 'entry_date')),
            'severity': 'WARNING' if entries.count() > 10 else 'OK',
        }

    @staticmethod
    def find_postings_in_closed_periods(branch=None):
        """
        Find posted journal entries that are assigned to closed accounting periods.
        """
        entries = JournalEntry.objects.filter(status='posted', accounting_period__is_closed=True)
        if branch:
            entries = entries.filter(branch=branch)

        return {
            'closed_period_postings_count': entries.count(),
            'entries': list(entries.values('id', 'reference', 'entry_date', 'accounting_period__start_date', 'accounting_period__end_date')),
            'severity': 'CRITICAL' if entries.count() > 0 else 'OK',
        }

    @staticmethod
    def find_payments_without_gl_entries(branch=None):
        """
        Find payments that don't have corresponding GL entries
        """
        payments = Payment.objects.filter(journal_entry__isnull=True)
        if branch:
            payments = payments.filter(order__branch=branch)

        supplier_payments = PurchasePayment.objects.filter(journal_entry__isnull=True)
        if branch:
            supplier_payments = supplier_payments.filter(branch=branch)

        return {
            'customer_payments_without_gl': payments.count(),
            'supplier_payments_without_gl': supplier_payments.count(),
            'severity': 'CRITICAL' if (payments.count() + supplier_payments.count()) > 0 else 'OK',
            'details': {
                'customer_payment_ids': list(payments.values_list('id', flat=True)[:10]),
                'supplier_payment_ids': list(supplier_payments.values_list('id', flat=True)[:10]),
            }
        }

    @staticmethod
    def run_full_reconciliation(branch=None, as_of_date=None, persist=False):
        """
        Run complete reconciliation suite
        """
        results = {
            'timestamp': timezone.now(),
            'branch': branch.name if branch else 'All Branches',
            'as_of_date': as_of_date or date.today(),
            'reconciliations': {},
        }

        # Core balance reconciliations
        results['reconciliations']['ar_balance'] = ReconciliationService.reconcile_ar_balance(branch, as_of_date)
        results['reconciliations']['ap_balance'] = ReconciliationService.reconcile_ap_balance(branch, as_of_date)
        results['reconciliations']['cash_balance'] = ReconciliationService.reconcile_cash_balance(branch, as_of_date)
        results['reconciliations']['inventory_valuation'] = ReconciliationService.reconcile_inventory_valuation(branch, as_of_date)

        # Integrity checks
        results['reconciliations']['unbalanced_entries'] = ReconciliationService.find_unbalanced_entries(branch)
        results['reconciliations']['orphaned_lines'] = ReconciliationService.find_orphaned_journal_lines()
        results['reconciliations']['duplicate_references'] = ReconciliationService.find_duplicate_references(branch)
        results['reconciliations']['missing_source_links'] = ReconciliationService.find_missing_source_links(branch)
        results['reconciliations']['closed_period_postings'] = ReconciliationService.find_postings_in_closed_periods(branch)
        results['reconciliations']['payments_without_gl'] = ReconciliationService.find_payments_without_gl_entries(branch)

        # Overall health assessment
        critical_issues = sum(1 for r in results['reconciliations'].values() if r.get('severity') == 'CRITICAL')
        warning_issues = sum(1 for r in results['reconciliations'].values() if r.get('severity') == 'WARNING')

        results['summary'] = {
            'overall_health': 'CRITICAL' if critical_issues > 0 else 'WARNING' if warning_issues > 0 else 'HEALTHY',
            'critical_issues': critical_issues,
            'warning_issues': warning_issues,
            'total_checks': len(results['reconciliations']),
        }

        if persist:
            run = ReconciliationRun.objects.create(
                branch=branch,
                as_of_date=results['as_of_date'],
                status='completed',
                summary=results['summary'],
                issues=[{
                    'check': key,
                    'severity': result.get('severity'),
                    'details': result,
                } for key, result in results['reconciliations'].items()],
                completed_at=timezone.now(),
            )
            results['run_id'] = run.id

        return results

    @staticmethod
    def get_reconciliation_report(branch=None, as_of_date=None):
        """
        Generate human-readable reconciliation report
        """
        results = ReconciliationService.run_full_reconciliation(branch, as_of_date)

        report = f"""
FINANCIAL RECONCILIATION REPORT
===============================
Branch: {results['branch']}
As Of: {results['as_of_date']}
Generated: {results['timestamp']}

OVERALL HEALTH: {results['summary']['overall_health']}
Critical Issues: {results['summary']['critical_issues']}
Warning Issues: {results['summary']['warning_issues']}
Total Checks: {results['summary']['total_checks']}

DETAILED RESULTS:
"""

        for check_name, check_result in results['reconciliations'].items():
            status = "✓" if check_result.get('severity') == 'OK' else "⚠" if check_result.get('severity') == 'WARNING' else "❌"
            report += f"\n{status} {check_name.upper().replace('_', ' ')}: {check_result.get('severity', 'UNKNOWN')}"

            if 'variance' in check_result:
                report += f"\n   Variance: {check_result['variance']}"

            if check_result.get('severity') != 'OK':
                if 'unbalanced_count' in check_result:
                    report += f"\n   Count: {check_result['unbalanced_count']}"
                if 'orphaned_count' in check_result:
                    report += f"\n   Count: {check_result['orphaned_count']}"
                if 'missing_links_count' in check_result:
                    report += f"\n   Count: {check_result['missing_links_count']}"

        return report