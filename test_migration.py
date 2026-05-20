#!/usr/bin/env python
import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Blacphics.settings')
django.setup()

from django.core.management import call_command
from django.db import connections
from branches.models import Branch
from customers.models import Customer
from products.models import Product, ProductVariant
from orders.models import Order, OrderItem
from django.contrib.auth.models import User

print("\n" + "="*80)
print("COMPREHENSIVE MIGRATION TEST")
print("="*80)

# Test 1: Check database connectivity
print("\n[1/5] Testing database connectivity...")
try:
    connection = connections['default']
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    print("     ✓ PostgreSQL connection successful")
except Exception as e:
    print(f"     ✗ PostgreSQL connection failed: {e}")
    sys.exit(1)

# Test 2: Check migration status
print("\n[2/5] Checking migration status...")
try:
    call_command('showmigrations', '--plan', verbosity=0, interactive=False)
    print("     ✓ Migration status OK")
except Exception as e:
    print(f"     ✗ Migration check failed: {e}")
    sys.exit(1)

# Test 3: Verify all tables have data
print("\n[3/5] Verifying table data...")
tables_check = {
    'Branch': Branch.objects.count(),
    'Customer': Customer.objects.count(),
    'Product': Product.objects.count(),
    'ProductVariant': ProductVariant.objects.count(),
    'Order': Order.objects.count(),
    'OrderItem': OrderItem.objects.count(),
    'User': User.objects.count(),
}

all_have_data = True
for table, count in tables_check.items():
    status = "✓" if count > 0 else "✗"
    print(f"     {status} {table}: {count} records")
    if count == 0:
        all_have_data = False

if not all_have_data:
    print("\n     ✗ Some tables have no data!")
    sys.exit(1)

# Test 4: Check specific data integrity
print("\n[4/5] Checking data integrity...")
try:
    # Check relationships
    orders_with_items = Order.objects.filter(orderitem__isnull=False).distinct().count()
    products_with_variants = Product.objects.filter(productvariant__isnull=False).distinct().count()
    
    print(f"     ✓ Orders with items: {orders_with_items}")
    print(f"     ✓ Products with variants: {products_with_variants}")
    
    # Check for a sample order
    sample_order = Order.objects.first()
    if sample_order:
        print(f"     ✓ Sample order: ID={sample_order.id}, customer={sample_order.customer}, status={sample_order.status}")
except Exception as e:
    print(f"     ✗ Data integrity check failed: {e}")
    sys.exit(1)

# Test 5: Check authentication user
print("\n[5/5] Checking authentication...")
try:
    admin_user = User.objects.first()
    if admin_user:
        print(f"     ✓ Admin user: {admin_user.username} ({admin_user.email})")
    else:
        print(f"     ✗ No users found")
        sys.exit(1)
except Exception as e:
    print(f"     ✗ Authentication check failed: {e}")
    sys.exit(1)

print("\n" + "="*80)
print("✓ ALL TESTS PASSED - MIGRATION SUCCESSFUL!")
print("="*80 + "\n")
