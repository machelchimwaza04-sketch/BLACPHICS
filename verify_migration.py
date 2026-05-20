#!/usr/bin/env python
import os
import django
from django.db import connections

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Blacphics.settings')
django.setup()

from branches.models import Branch
from customers.models import Customer
from products.models import Product, ProductVariant
from orders.models import Order, OrderItem
from django.contrib.auth.models import User

# Define expected counts
expected_counts = {
    'branches_branch': 5,
    'customers_customer': 100,
    'products_product': 250,
    'products_productvariant': 503,
    'orders_order': 67,
    'orders_orderitem': 25,
    'auth_user': 1,
}

# Actual counts from models
actual_counts = {
    'branches_branch': Branch.objects.count(),
    'customers_customer': Customer.objects.count(),
    'products_product': Product.objects.count(),
    'products_productvariant': ProductVariant.objects.count(),
    'orders_order': Order.objects.count(),
    'orders_orderitem': OrderItem.objects.count(),
    'auth_user': User.objects.count(),
}

# Print comparison table
print("\n" + "="*80)
print("MIGRATION VERIFICATION - PostgreSQL Row Counts")
print("="*80)
print(f"{'Table':<30} {'Expected':<15} {'Actual':<15} {'Status':<10}")
print("-"*80)

all_match = True
for table, expected in expected_counts.items():
    actual = actual_counts[table]
    status = "✓ OK" if expected == actual else "✗ MISMATCH"
    if expected != actual:
        all_match = False
    print(f"{table:<30} {expected:<15} {actual:<15} {status:<10}")

print("-"*80)
print(f"\nTotal records in SQLite export: 990")
print(f"Total records loaded to PostgreSQL: {sum(actual_counts.values())}")
print(f"\n{'OVERALL STATUS:':<40} {'✓ ALL MATCH!' if all_match else '✗ MISMATCHES FOUND'}")
print("="*80 + "\n")
