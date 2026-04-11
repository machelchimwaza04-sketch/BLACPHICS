from django.core.mail import send_mail
from django.conf import settings
from .models import ProductVariant


def get_low_stock_alerts(branch_id=None):
    """
    Returns list of alert dicts for variants that are low or out of stock.
    """
    variants = ProductVariant.objects.select_related('product', 'product__branch')
    if branch_id:
        variants = variants.filter(product__branch_id=branch_id)

    alerts = []
    for v in variants:
        status = v.stock_status
        if status in ('low_stock', 'out_of_stock'):
            alerts.append({
                'id': v.id,
                'product_id': v.product.id,
                'product_name': v.product.name,
                'variant': f"{v.size} / {v.color}",
                'available_quantity': v.available_quantity,
                'stock_quantity': v.stock_quantity,
                'committed_quantity': v.committed_quantity,
                'threshold': v.product.low_stock_threshold,
                'status': status,
                'branch_id': v.product.branch_id,
                'branch_name': str(v.product.branch),
            })

    # Sort: out_of_stock first, then low_stock
    alerts.sort(key=lambda x: 0 if x['status'] == 'out_of_stock' else 1)
    return alerts


def send_low_stock_email(branch):
    """
    Sends a low stock alert email to the branch manager.
    """
    if not branch.manager_email:
        return

    alerts = get_low_stock_alerts(branch_id=branch.id)
    if not alerts:
        return

    out_of_stock = [a for a in alerts if a['status'] == 'out_of_stock']
    low_stock = [a for a in alerts if a['status'] == 'low_stock']

    lines = [f"Low Stock Alert — {branch.name}\n"]

    if out_of_stock:
        lines.append("OUT OF STOCK:")
        for a in out_of_stock:
            lines.append(f"  • {a['product_name']} ({a['variant']}) — 0 units left")

    if low_stock:
        lines.append("\nLOW STOCK:")
        for a in low_stock:
            lines.append(f"  • {a['product_name']} ({a['variant']}) — {a['available_quantity']} units left (threshold: {a['threshold']})")

    lines.append(f"\nTotal alerts: {len(alerts)}")
    lines.append("Please restock these items as soon as possible.")

    send_mail(
        subject=f"[Blacphics] Low Stock Alert — {branch.name}",
        message="\n".join(lines),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[branch.manager_email],
        fail_silently=True,
    )