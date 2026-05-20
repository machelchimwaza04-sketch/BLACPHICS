import django
from rest_framework.test import APIClient
from orders.models import Order

django.setup()
client = APIClient()
order = Order.objects.first()
print('order id', order.id)
url = f'/api/orders/{order.id}/'
payload = {
    'id': order.id,
    'order_number': order.order_number,
    'transaction_type': order.transaction_type,
    'status': 'confirmed' if order.status != 'confirmed' else 'pending',
    'payment_status': order.payment_status,
    'payment_method': order.payment_method,
    'total_amount': str(order.total_amount),
    'discount_amount': str(order.discount_amount),
    'discount_reason': order.discount_reason,
    'amount_paid': str(order.amount_paid),
    'deposit_amount': str(order.deposit_amount),
    'notes': order.notes,
    'estimated_completion': order.estimated_completion.isoformat() if order.estimated_completion else None,
    'branch': order.branch_id,
    'customer': order.customer_id,
    'discount_approved_by': order.discount_approved_by_id,
    'created_by': order.created_by_id,
}
print('payload keys', list(payload.keys()))
response = client.put(url, payload, format='json')
print('status', response.status_code)
print('data', response.data)
