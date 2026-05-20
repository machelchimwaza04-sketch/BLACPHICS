#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Blacphics.settings')
django.setup()

from django.core.management import call_command
from django.db.models.signals import post_save
from orders.models import OrderItem
from orders.signals import deduct_stock_for_quick_sale

# Temporarily disconnect the signal that causes issues
print("Disconnecting signal: deduct_stock_for_quick_sale...")
post_save.disconnect(deduct_stock_for_quick_sale, sender=OrderItem)

try:
    print("Loading orders data...")
    call_command('loaddata', 'full_data_export_orders.json')
    print("Orders data loaded successfully!")
finally:
    # Reconnect the signal
    print("Reconnecting signal: deduct_stock_for_quick_sale...")
    post_save.connect(deduct_stock_for_quick_sale, sender=OrderItem)
