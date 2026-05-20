#!/usr/bin/env python
import os
import sys
import django
from io import StringIO
from django.core.management import call_command

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Blacphics.settings')
django.setup()

# Run dumpdata for all except orders
print("Exporting data without orders...")
out = StringIO()
call_command('dumpdata', 
    database='sqlite_backup',
    natural_foreign=True,
    natural_primary=True,
    exclude=['contenttypes', 'auth.permission', 'orders'],
    indent=2,
    stdout=out
)
with open('full_data_export_no_orders.json', 'w', encoding='utf-8') as f:
    f.write(out.getvalue())
print(f"Exported {len(out.getvalue().splitlines())} lines to full_data_export_no_orders.json")

# Run dumpdata for orders only
print("Exporting orders data...")
out2 = StringIO()
call_command('dumpdata',
    'orders',
    database='sqlite_backup',
    natural_foreign=True,
    natural_primary=True,
    indent=2,
    stdout=out2
)
with open('full_data_export_orders.json', 'w', encoding='utf-8') as f:
    f.write(out2.getvalue())
print(f"Exported {len(out2.getvalue().splitlines())} lines to full_data_export_orders.json")
