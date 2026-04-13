from django.db.models import Sum, F, DecimalField, ExpressionWrapper

from suppliers.models import Supplier, Purchase


def supplier_summary_rows():
    """
    One row per active supplier with aggregates for the summary endpoint.
    """
    suppliers = Supplier.objects.filter(is_active=True).order_by('name')
    rows = []
    for s in suppliers:
        purchases = Purchase.objects.filter(supplier=s)
        owed_expr = ExpressionWrapper(
            F('total_amount') - F('amount_paid'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        agg = purchases.aggregate(total_owed=Sum(owed_expr))
        total_owed = float(agg['total_owed'] or 0)
        has_overdue = purchases.filter(
            payment_status__in=['unpaid', 'partial'],
            status='received',
        ).exists()
        if total_owed == 0:
            account_status = 'clear'
        elif has_overdue:
            account_status = 'overdue'
        else:
            account_status = 'outstanding'
        rows.append({
            'id': s.id,
            'name': s.name,
            'contact_person': s.contact_person,
            'phone': s.phone,
            'email': s.email,
            'total_owed': round(total_owed, 2),
            'total_purchases': purchases.count(),
            'account_status': account_status,
        })
    return rows
