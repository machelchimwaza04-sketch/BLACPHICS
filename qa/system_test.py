import os
import sys
import random
import time
import uuid
import threading
from datetime import timedelta

# Configure Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Blacphics.settings')
import django
django.setup()

from django.db import transaction
from django.utils import timezone
from django.test import Client
from rest_framework.test import APIClient

from branches.models import Branch
from customers.models import Customer
from products.models import Category, Product, ProductVariant
from orders.models import Order, OrderItem, Payment, StockReservation, OrderIdempotencyRecord
from finance.tasks import create_daily_snapshots

REPORT = []


def log(line):
    print(line)
    REPORT.append(line)


def seed_data():
    log('--- Seeding test data ---')
    Branch.objects.all().delete()
    Customer.objects.all().delete()
    Category.objects.all().delete()
    ProductVariant.objects.all().delete()
    Product.objects.all().delete()
    Order.objects.all().delete()
    OrderItem.objects.all().delete()
    Payment.objects.all().delete()
    StockReservation.objects.all().delete()
    OrderIdempotencyRecord.objects.all().delete()

    cities = ['Lagos', 'Nairobi', 'Accra', 'Kampala', 'Cairo']
    branches = []
    for i, city in enumerate(cities, start=1):
        branch = Branch.objects.create(
            name=f'Branch {i}',
            city=city,
            address=f'{i} Main Street, {city}',
            phone=f'+12345678{i:02d}',
            email=f'branch{i}@example.com',
            manager_email=f'manager{i}@example.com',
        )
        branches.append(branch)
    log(f'Created {len(branches)} branches')

    categories = []
    for i in range(1, 11):
        categories.append(Category.objects.create(name=f'Category {i}', description=f'Description {i}'))
    log(f'Created {len(categories)} categories')

    products = []
    variants = []
    sizes = ['S', 'M', 'L', 'XL']
    colors = ['Red', 'Blue', 'Green', 'Black']
    for branch in branches:
        for pnum in range(1, 51):
            product = Product.objects.create(
                branch=branch,
                category=random.choice(categories),
                name=f'Product {branch.id}-{pnum}',
                description='Test product',
                item_type=random.choice(['plain', 'customizable']),
                base_price=random.uniform(10, 200),
                customization_price=random.uniform(0, 80),
                stock_quantity=0,
                low_stock_threshold=5,
                is_active=True,
            )
            products.append(product)
            variant_count = random.choice([1, 2, 3])
            seen = set()
            product_stock = 0
            for vnum in range(variant_count):
                choice_key = None
                while choice_key is None or choice_key in seen:
                    choice_key = (random.choice(sizes), random.choice(colors))
                seen.add(choice_key)
                size, color = choice_key
                stock_quantity = random.choice([0, 1, 2, 5, 10, 20, 50])
                variant = ProductVariant.objects.create(
                    product=product,
                    size=size,
                    color=color,
                    stock_quantity=stock_quantity,
                    committed_quantity=0,
                    cost_price=random.uniform(5, 90),
                    extra_price=random.uniform(0, 30),
                    is_available=stock_quantity > 0,
                )
                variants.append(variant)
                product_stock += stock_quantity
            product.stock_quantity = product_stock
            product.save(update_fields=['stock_quantity'])
    log(f'Created {len(products)} products with {len(variants)} variants')

    customers = []
    for i in range(1, 101):
        branch = random.choice(branches)
        customers.append(Customer.objects.create(
            branch=branch,
            first_name=f'Customer{i}',
            last_name='Test',
            email=f'customer{i}@example.com',
            phone=f'+234700{i:04d}',
            gender=random.choice(['male', 'female', 'other']),
            address=f'{i} Test Lane, {branch.city}',
        ))
    log(f'Created {len(customers)} registered customers')

    # Create prior orders so there is history
    prior_orders = 0
    for _ in range(40):
        branch = random.choice(branches)
        customer = random.choice(customers)
        status = random.choice(['completed', 'pending', 'confirmed'])
        transaction_type = random.choice(['quick_sale', 'custom_order'])
        order = Order.objects.create(
            branch=branch,
            customer=customer,
            order_number=Order.generate_order_number(branch.id),
            transaction_type=transaction_type,
            status=status,
            payment_status='paid' if status == 'completed' else 'partial',
            payment_method=random.choice(['cash', 'card', 'mobile_money', 'bank_transfer']),
            total_amount=random.uniform(50, 500),
            discount_amount=random.choice([0.0, 5.0, 10.0]),
            amount_paid=random.uniform(20, 500),
            notes='Historical order',
            estimated_completion=(timezone.now().date() + timedelta(days=7)) if transaction_type == 'custom_order' else None,
        )
        prior_orders += 1
    log(f'Created {prior_orders} prior historical orders')

    return {
        'branches': branches,
        'categories': categories,
        'products': products,
        'variants': variants,
        'customers': customers,
    }


def api_client():
    client = APIClient(raise_request_exception=False)
    client.defaults['HTTP_HOST'] = 'localhost'
    return client


def create_order_payload(branch, customer=None, guest=None, transaction_type='quick_sale', status='pending', payment_method='cash', total_amount=0.0, discount_amount=0.0, amount_paid=0.0):
    data = {
        'branch': branch.id,
        'customer': customer.id if customer else None,
        'order_number': Order.generate_order_number(branch.id),
        'transaction_type': transaction_type,
        'status': status,
        'payment_method': payment_method,
        'total_amount': round(total_amount, 2),
        'discount_amount': round(discount_amount, 2),
        'amount_paid': round(amount_paid, 2),
        'notes': 'Automated QA order',
        'estimated_completion': None,
        'payment_status': 'paid' if amount_paid >= total_amount else 'partial' if amount_paid > 0 else 'unpaid',
    }
    if guest:
        data.update({
            'guest_email': guest.get('email', ''),
            'guest_phone': guest.get('phone', ''),
            'guest_address': guest.get('address', ''),
        })
    return data


def create_order_item_payload(order_id, product, variant, quantity, unit_price):
    return {
        'order': order_id,
        'product': product.id,
        'variant': variant.id if variant else None,
        'quantity': quantity,
        'unit_price': round(unit_price, 2),
        'override_price': None,
        'override_reason': '',
        'customization_details': 'QA item',
        'customization_price': 0.0,
        'stock_status_at_sale': variant.stock_status if variant else 'in_stock',
        'services': [],
    }


def safe_api_post(client, path, payload):
    response = client.post(path, payload, format='json')
    try:
        return response.status_code, response.json()
    except Exception:
        return response.status_code, response.content.decode('utf-8', errors='replace')


def safe_api_patch(client, path, payload):
    response = client.patch(path, payload, format='json')
    try:
        return response.status_code, response.json()
    except Exception:
        return response.status_code, response.content.decode('utf-8', errors='replace')


def test_create_order_normal_user(data):
    log('--- Test: Create order (normal user) ---')
    client = api_client()
    branch = random.choice(data['branches'])
    customer = random.choice(data['customers'])
    product = random.choice([v for v in data['variants'] if v.stock_quantity > 0])
    payload = create_order_payload(branch, customer=customer, transaction_type='quick_sale', status='completed', payment_method='card', total_amount=product.product.base_price, amount_paid=product.product.base_price)
    status, body = safe_api_post(client, '/api/orders/', payload)
    if status != 201:
        log(f'FAIL create order returned {status}: {body}')
        return False
    order_id = body['id']
    item_payload = create_order_item_payload(order_id, product.product, product, 1, product.product.base_price + product.extra_price)
    item_status, item_body = safe_api_post(client, '/api/order-items/', item_payload)
    if item_status != 201:
        log(f'FAIL create order item returned {item_status}: {item_body}')
        return False
    log(f'PASS created order {order_id} for normal user')
    return order_id


def test_create_order_guest_checkout(data):
    log('--- Test: Create order (guest checkout) ---')
    client = api_client()
    branch = random.choice(data['branches'])
    variant = random.choice([v for v in data['variants'] if v.stock_quantity > 0])
    guest = {'email': 'guest@example.com', 'phone': '+8005551234', 'address': '123 Guest Road'}
    payload = create_order_payload(branch, customer=None, guest=guest, transaction_type='quick_sale', status='completed', payment_method='cash', total_amount=variant.product.base_price, amount_paid=variant.product.base_price)
    status, body = safe_api_post(client, '/api/orders/', payload)
    if status != 201:
        log(f'FAIL guest order returned {status}: {body}')
        return False
    order_id = body['id']
    item_payload = create_order_item_payload(order_id, variant.product, variant, 1, variant.product.base_price + variant.extra_price)
    item_status, item_body = safe_api_post(client, '/api/order-items/', item_payload)
    if item_status != 201:
        log(f'FAIL guest order item returned {item_status}: {item_body}')
        return False
    log(f'PASS guest checkout order {order_id}')
    return order_id


def test_insufficient_stock(data):
    log('--- Test: Create order with insufficient stock ---')
    client = api_client()
    branch = random.choice(data['branches'])
    variant = random.choice([v for v in data['variants'] if v.stock_quantity >= 0])
    quantity = variant.stock_quantity + 10
    payload = create_order_payload(branch, customer=random.choice(data['customers']), transaction_type='quick_sale', status='completed', payment_method='cash', total_amount=variant.product.base_price * quantity, amount_paid=variant.product.base_price * quantity)
    status, body = safe_api_post(client, '/api/orders/', payload)
    if status != 201:
        log(f'PASS order creation rejected with status {status}')
        return True
    order_id = body['id']
    item_payload = create_order_item_payload(order_id, variant.product, variant, quantity, variant.product.base_price)
    item_status, item_body = safe_api_post(client, '/api/order-items/', item_payload)
    if item_status == 201:
        log(f'FAIL insufficient stock order item created: {item_body}')
        return False
    log(f'PASS insufficient stock rejected at item creation with status {item_status}')
    return True


def test_duplicate_idempotency(data):
    log('--- Test: Retry same order with idempotency key ---')
    client = api_client()
    branch = random.choice(data['branches'])
    product = random.choice([v for v in data['variants'] if v.stock_quantity > 0])
    key = str(uuid.uuid4())
    payload = create_order_payload(branch, customer=random.choice(data['customers']), transaction_type='quick_sale', status='completed', payment_method='cash', total_amount=product.product.base_price, amount_paid=product.product.base_price)
    payload['idempotency_key'] = key
    status1, body1 = safe_api_post(client, '/api/orders/', payload)
    status2, body2 = safe_api_post(client, '/api/orders/', payload)
    if status1 != 201:
        log(f'FAIL first request returned {status1}: {body1}')
        return False
    if status2 == 201 and body1.get('id') != body2.get('id'):
        log(f'FAIL duplicate request created second order: {body1.get("id")} and {body2.get("id")}')
        return False
    log(f'PASS duplicate idempotency behavior observed: {status1}, {status2}')
    return status1 == 201 and (status2 != 201 or body1.get('id') == body2.get('id'))


def test_payment_flows(data):
    log('--- Test: Payment flows ---')
    client = api_client()
    branch = random.choice(data['branches'])
    variant = random.choice([v for v in data['variants'] if v.stock_quantity > 0])
    order_payload = create_order_payload(branch, customer=random.choice(data['customers']), transaction_type='quick_sale', status='completed', payment_method='card', total_amount=variant.product.base_price, amount_paid=0.0)
    status, body = safe_api_post(client, '/api/orders/', order_payload)
    if status != 201:
        log(f'FAIL payment order create returned {status}: {body}')
        return False
    order_id = body['id']
    item_payload = create_order_item_payload(order_id, variant.product, variant, 1, variant.product.base_price + variant.extra_price)
    item_status, item_body = safe_api_post(client, '/api/order-items/', item_payload)
    if item_status != 201:
        log(f'FAIL payment order item create returned {item_status}: {item_body}')
        return False
    pay_status, pay_body = safe_api_post(client, f'/api/orders/{order_id}/add_payment/', {'amount': variant.product.base_price, 'method': 'card', 'payment_type': 'payment', 'notes': 'QA payment'})
    if pay_status != 200:
        log(f'FAIL payment endpoint returned {pay_status}: {pay_body}')
        return False
    if pay_body.get('payment_status') != 'paid':
        log(f'WARN payment_status not paid after full payment: {pay_body.get("payment_status")}')
    log(f'PASS payment success for order {order_id}')
    bad_status, bad_body = safe_api_post(client, f'/api/orders/{order_id}/add_payment/', {'amount': -10, 'method': 'cash', 'payment_type': 'payment', 'notes': 'Invalid'})
    if bad_status == 200:
        log(f'FAIL invalid payment accepted: {bad_body}')
        return False
    log(f'PASS invalid payment rejected with status {bad_status}')
    return True


def test_custom_order_reservation_and_release(data):
    log('--- Test: Custom order reservation and release ---')
    client = api_client()
    branch = random.choice(data['branches'])
    variant = random.choice([v for v in data['variants'] if v.stock_quantity >= 2])
    order_payload = create_order_payload(branch, customer=random.choice(data['customers']), transaction_type='custom_order', status='pending', payment_method='bank_transfer', total_amount=variant.product.base_price * 1, amount_paid=0.0)
    status, body = safe_api_post(client, '/api/orders/', order_payload)
    if status != 201:
        log(f'FAIL custom order create returned {status}: {body}')
        return False
    order_id = body['id']
    item_payload = create_order_item_payload(order_id, variant.product, variant, 1, variant.product.base_price)
    item_status, item_body = safe_api_post(client, '/api/order-items/', item_payload)
    if item_status != 201:
        log(f'FAIL custom order item create returned {item_status}: {item_body}')
        return False
    patch_status, patch_body = safe_api_patch(client, f'/api/orders/{order_id}/', {'status': 'confirmed'})
    if patch_status != 200:
        log(f'FAIL order confirm returned {patch_status}: {patch_body}')
        return False
    variant.refresh_from_db()
    if variant.committed_quantity < 1:
        log(f'FAIL stock not committed on confirm, committed_quantity={variant.committed_quantity}')
        return False
    log('PASS stock committed on confirm')
    cancel_status, cancel_body = safe_api_patch(client, f'/api/orders/{order_id}/', {'status': 'cancelled'})
    if cancel_status != 200:
        log(f'FAIL cancel returned {cancel_status}: {cancel_body}')
        return False
    variant.refresh_from_db()
    if variant.committed_quantity != 0:
        log(f'FAIL committed_quantity not released after cancel: {variant.committed_quantity}')
        return False
    log('PASS release after cancel')
    return True


def test_concurrent_orders(data, concurrency=10):
    log('--- Test: Concurrent order creation on same product ---')
    product_variants = [v for v in data['variants'] if v.stock_quantity >= concurrency and v.committed_quantity == 0]
    if not product_variants:
        log('SKIP no suitable variants with sufficient stock for concurrency')
        return False
    variant = random.choice(product_variants)
    stock_before = variant.stock_quantity
    threads = []
    responses = []

    def make_order(thread_id):
        client = APIClient()
        client.defaults['HTTP_HOST'] = 'localhost'
        branch = variant.product.branch
        payload = create_order_payload(branch, customer=random.choice(data['customers']), transaction_type='quick_sale', status='completed', payment_method='cash', total_amount=variant.product.base_price, amount_paid=variant.product.base_price)
        status, body = safe_api_post(client, '/api/orders/', payload)
        if status == 201 and isinstance(body, dict) and body.get('id'):
            order_id = body['id']
            item_payload = create_order_item_payload(order_id, variant.product, variant, 1, variant.product.base_price)
            item_status, item_body = safe_api_post(client, '/api/order-items/', item_payload)
            responses.append((thread_id, item_status, item_body))
        else:
            responses.append((thread_id, status, body))

    for i in range(concurrency):
        t = threading.Thread(target=make_order, args=(i,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    variant.refresh_from_db()
    successes = [r for r in responses if r[1] == 201]
    failures = [r for r in responses if r[1] != 201]
    log(f'Concurrency test: {len(successes)} successes, {len(failures)} failures, stock_before={stock_before}, stock_after={variant.stock_quantity}')
    if variant.stock_quantity < 0:
        log('FAIL negative stock detected')
        return False
    if len(successes) > stock_before:
        log('FAIL more successful orders than available stock')
        return False
    log('PASS concurrent orders maintained stock bounds')
    return True


def test_api_performance(data):
    log('--- Test: API performance ---')
    client = api_client()
    branch = random.choice(data['branches'])
    metrics = {}
    start = time.perf_counter()
    r = client.get(f'/api/products/?branch={branch.id}')
    metrics['products_ms'] = (time.perf_counter() - start) * 1000
    metrics['products_status'] = r.status_code
    metrics['products_payload_size'] = len(r.content)
    start = time.perf_counter()
    r = client.get(f'/api/orders/?branch={branch.id}')
    metrics['orders_ms'] = (time.perf_counter() - start) * 1000
    metrics['orders_status'] = r.status_code
    metrics['orders_payload_size'] = len(r.content)
    payload = create_order_payload(branch, customer=random.choice(data['customers']), transaction_type='quick_sale', status='pending', payment_method='cash', total_amount=10.0, amount_paid=0.0)
    start = time.perf_counter()
    status, body = safe_api_post(client, '/api/orders/', payload)
    metrics['checkout_ms'] = (time.perf_counter() - start) * 1000
    metrics['checkout_status'] = status
    log(f"Product list: {metrics['products_ms']:.1f}ms status={metrics['products_status']} size={metrics['products_payload_size']}")
    log(f"Order list: {metrics['orders_ms']:.1f}ms status={metrics['orders_status']} size={metrics['orders_payload_size']}")
    log(f"Checkout endpoint: {metrics['checkout_ms']:.1f}ms status={metrics['checkout_status']} payload_size={len(str(payload))}")
    return True


def test_background_tasks():
    log('--- Test: Background task execution ---')
    import io
    try:
        # Ensure task prints can safely render unicode in this environment.
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

    try:
        result = create_daily_snapshots()
        log(f'PASS created daily snapshots task result: {result}')
        return True
    except Exception as exc:
        log(f'FAIL background task raised exception: {exc}')
        return False


def verify_data_integrity():
    log('--- Test: Data integrity checks ---')
    negatives = []
    for variant in ProductVariant.objects.all():
        if variant.stock_quantity < 0 or variant.committed_quantity < 0:
            negatives.append((variant.id, variant.stock_quantity, variant.committed_quantity))
    if negatives:
        log(f'FAIL negative stock/commit detected: {negatives[:5]}')
        return False
    duplicates = []
    seen = {}
    for order in Order.objects.all():
        key = (order.branch_id, order.order_number)
        if key in seen:
            duplicates.append(key)
        else:
            seen[key] = order.id
    if duplicates:
        log(f'FAIL duplicate order numbers found: {duplicates[:5]}')
        return False
    orphans = []
    for item in OrderItem.objects.all():
        if not Order.objects.filter(id=item.order_id).exists():
            orphans.append(item.id)
    if orphans:
        log(f'FAIL orphan order items found: {orphans[:5]}')
        return False
    log('PASS data integrity checks')
    return True


def run_all():
    data = seed_data()
    results = []
    results.append(('create_order_normal_user', bool(test_create_order_normal_user(data))))
    results.append(('create_order_guest_checkout', bool(test_create_order_guest_checkout(data))))
    results.append(('create_order_insufficient_stock', bool(test_insufficient_stock(data))))
    results.append(('duplicate_idempotency', bool(test_duplicate_idempotency(data))))
    results.append(('payment_flows', bool(test_payment_flows(data))))
    results.append(('custom_order_reservation', bool(test_custom_order_reservation_and_release(data))))
    results.append(('concurrency', bool(test_concurrent_orders(data, concurrency=20))))
    results.append(('api_performance', bool(test_api_performance(data))))
    results.append(('background_tasks', bool(test_background_tasks())))
    results.append(('data_integrity', bool(verify_data_integrity())))

    log('--- Summary ---')
    for name, passed in results:
        log(f'{name}: {"PASS" if passed else "FAIL"}')
    failed = [name for name, passed in results if not passed]
    log(f'Failed count: {len(failed)}')
    return failed


if __name__ == '__main__':
    failed_names = run_all()
    print('\n'.join(REPORT))
    if failed_names:
        print(f'FAILURES: {failed_names}')
        sys.exit(1)
    sys.exit(0)
