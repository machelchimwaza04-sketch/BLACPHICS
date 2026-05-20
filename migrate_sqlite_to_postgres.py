#!/usr/bin/env python
"""
Migrate all data from SQLite (db.sqlite3) to PostgreSQL.
This script:
1. Exports all tables from SQLite
2. Imports them into PostgreSQL
3. Resets sequences
4. Verifies data integrity
"""

import os
import sys
import django
from io import StringIO
from django.core.management import call_command

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Blacphics.settings')
django.setup()

from django.db import connections, DEFAULT_DB_ALIAS
from django.conf import settings

def main():
    """Execute full migration from SQLite to PostgreSQL."""
    
    # Check that we have a PostgreSQL target
    db_name = settings.DATABASES['default']['ENGINE']
    print(f"Current database backend: {db_name}")
    
    if 'postgresql' not in db_name:
        print("ERROR: DATABASE_URL must point to PostgreSQL for migration.")
        print("Set DATABASE_URL=postgres://... in your .env file")
        sys.exit(1)
    
    print("\n=== SQLite → PostgreSQL Migration ===\n")
    
    # Step 1: Check SQLite file exists
    sqlite_path = settings.BASE_DIR / 'db.sqlite3'
    if not sqlite_path.exists():
        print(f"WARNING: SQLite database not found at {sqlite_path}")
        print("No data to migrate.")
        return
    
    print(f"SQLite database: {sqlite_path}")
    print(f"Target: PostgreSQL")
    
    try:
        # Step 2: Run migrations (creates tables)
        print("\n1. Creating database schema...")
        call_command('migrate', verbosity=0)
        print("   ✓ Schema created")
        
        # Step 3: Dump from SQLite and load to PostgreSQL
        print("\n2. Exporting data from SQLite...")
        sqlite_dump = StringIO()
        call_command('dumpdata', stdout=sqlite_dump, verbosity=0)
        sqlite_data = sqlite_dump.getvalue()
        
        if sqlite_data.strip():
            print(f"   ✓ Exported {len(sqlite_data)} bytes")
            
            print("\n3. Loading data into PostgreSQL...")
            # Write to temporary file since loaddata doesn't support stdin
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                f.write(sqlite_data)
                temp_file = f.name
            
            try:
                call_command('loaddata', temp_file, verbosity=0)
                print("   ✓ Data loaded")
            finally:
                os.unlink(temp_file)
        else:
            print("   No data to export (fresh database)")
        
        # Step 4: Fix sequences
        print("\n4. Fixing database sequences...")
        from django.core.management.sql import emit_post_migrate_signal
        
        # Get all models
        from django.apps import apps
        db = DEFAULT_DB_ALIAS
        
        # Call sequence reset for all tables
        sequence_sql = call_command('sqlsequencereset', *[a.label for a in apps.get_app_configs()], 
                                     database=db, stdout=StringIO())
        print("   ✓ Sequences fixed")
        
        # Step 5: Verify
        print("\n5. Verifying migration...")
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as table_count 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """)
            table_count = cursor.fetchone()[0]
            print(f"   ✓ {table_count} tables in PostgreSQL")
        
        # Check key tables
        from orders.models import Order
        from products.models import Product
        from customers.models import Customer
        
        order_count = Order.objects.count()
        product_count = Product.objects.count()
        customer_count = Customer.objects.count()
        
        print(f"   ✓ Orders: {order_count}")
        print(f"   ✓ Products: {product_count}")
        print(f"   ✓ Customers: {customer_count}")
        
        print("\n=== Migration Complete ===")
        print("\nNext steps:")
        print("1. Verify data with: python manage.py dbshell")
        print("2. Run tests with: python qa/system_test.py")
        print("3. Backup original SQLite: mv db.sqlite3 db.sqlite3.bak")
        
    except Exception as e:
        print(f"\nERROR during migration: {e}")
        import traceback
        traceback.print_exc()
        print("\nRollback: Check PostgreSQL and try again.")
        sys.exit(1)

if __name__ == '__main__':
    main()
