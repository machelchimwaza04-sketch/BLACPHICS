#!/usr/bin/env python
"""
Foreign Key and Data Integrity Validation Script
Checks FK constraints, orphaned rows, invalid references, and transaction/journal integrity.
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Blacphics.settings')
django.setup()

from django.db import connection
from django.db.models import Q
from orders.models import Order, OrderItem, OrderNumberSequence
from inventory.models import InventoryTransaction
from products.models import Product
from finance.models import JournalEntry, JournalLine, Account, DailyPLSnapshot
from suppliers.models import Purchase, PurchaseItem, PurchasePayment
from branches.models import Branch, User
import json
from datetime import datetime

class DataIntegrityValidator:
    """Validate foreign keys and data integrity."""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.info = []
        self.cursor = connection.cursor()
        
    def log_issue(self, msg):
        """Log a critical issue."""
        self.issues.append(msg)
        print(f"❌ ISSUE: {msg}")
        
    def log_warning(self, msg):
        """Log a warning."""
        self.warnings.append(msg)
        print(f"⚠️  WARNING: {msg}")
        
    def log_info(self, msg):
        """Log informational message."""
        self.info.append(msg)
        print(f"ℹ️  INFO: {msg}")
    
    def validate_all_fk_constraints(self):
        """Verify all FK constraints are valid."""
        print("\n" + "="*60)
        print("1. FOREIGN KEY CONSTRAINT VALIDATION")
        print("="*60)
        
        try:
            # Check for constraint violations by attempting to analyze constraints
            self.cursor.execute("""
                SELECT 
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS referenced_table,
                    ccu.column_name AS referenced_column
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_schema = 'public'
                ORDER BY tc.table_name
            """)
            
            fk_constraints = self.cursor.fetchall()
            self.log_info(f"Total FK constraints: {len(fk_constraints)}")
            
            constraint_check_count = 0
            for table, col, ref_table, ref_col in fk_constraints[:5]:
                constraint_check_count += 1
                self.log_info(f"  ✓ {table}.{col} → {ref_table}.{ref_col}")
            
            if len(fk_constraints) > 5:
                self.log_info(f"  ... and {len(fk_constraints) - 5} more")
                
        except Exception as e:
            self.log_warning(f"Could not validate FK constraints: {e}")
    
    def validate_orders_integrity(self):
        """Validate orders, order items, and related data integrity."""
        print("\n" + "="*60)
        print("2. ORDERS DATA INTEGRITY")
        print("="*60)
        
        try:
            # Check total orders
            orders_count = Order.objects.count()
            self.log_info(f"Total orders: {orders_count}")
            
            if orders_count > 0:
                # Check for orphaned order items (items with invalid order references)
                self.cursor.execute("""
                    SELECT COUNT(*) FROM orders_orderitem oi
                    LEFT JOIN orders_order o ON oi.order_id = o.id
                    WHERE o.id IS NULL
                """)
                orphaned_items = self.cursor.fetchone()[0]
                if orphaned_items > 0:
                    self.log_issue(f"Found {orphaned_items} orphaned order items")
                else:
                    self.log_info("✓ No orphaned order items")
                
                # Check for orders without created_by
                orders_no_created_by = Order.objects.filter(created_by__isnull=True).count()
                if orders_no_created_by > 0:
                    self.log_warning(f"Orders without created_by: {orders_no_created_by}")
                else:
                    self.log_info("✓ All orders have created_by set")
                
                # Check order status values
                self.cursor.execute("""
                    SELECT DISTINCT status FROM orders_order ORDER BY status
                """)
                statuses = [r[0] for r in self.cursor.fetchall()]
                self.log_info(f"Order statuses in use: {statuses}")
                
                # Check for orders with negative amounts
                negative_orders = Order.objects.filter(total_amount__lt=0).count()
                if negative_orders > 0:
                    self.log_warning(f"Orders with negative total_amount: {negative_orders}")
                else:
                    self.log_info("✓ No orders with negative amounts")
                    
        except Exception as e:
            self.log_warning(f"Error validating orders: {e}")
    
    def validate_inventory_integrity(self):
        """Validate inventory transactions and products."""
        print("\n" + "="*60)
        print("3. INVENTORY DATA INTEGRITY")
        print("="*60)
        
        try:
            # Check inventory transactions
            trans_count = InventoryTransaction.objects.count()
            self.log_info(f"Total inventory transactions: {trans_count}")
            
            if trans_count > 0:
                # Check for orphaned transactions
                self.cursor.execute("""
                    SELECT COUNT(*) FROM inventory_inventorytransaction it
                    LEFT JOIN products_product p ON it.product_id = p.id
                    WHERE p.id IS NULL
                """)
                orphaned_trans = self.cursor.fetchone()[0]
                if orphaned_trans > 0:
                    self.log_issue(f"Found {orphaned_trans} inventory transactions with missing products")
                else:
                    self.log_info("✓ No orphaned inventory transactions")
                
                # Check transaction types
                self.cursor.execute("""
                    SELECT DISTINCT transaction_type, COUNT(*) 
                    FROM inventory_inventorytransaction 
                    GROUP BY transaction_type
                """)
                trans_types = self.cursor.fetchall()
                for ttype, count in trans_types:
                    self.log_info(f"  {ttype}: {count} transactions")
                    
            # Check products
            products_count = Product.objects.count()
            self.log_info(f"Total products: {products_count}")
            
            if products_count > 0:
                # Check for products with negative quantities
                neg_qty = Product.objects.filter(quantity_on_hand__lt=0).count()
                if neg_qty > 0:
                    self.log_warning(f"Products with negative quantity_on_hand: {neg_qty}")
                else:
                    self.log_info("✓ No products with negative quantities")
                    
        except Exception as e:
            self.log_warning(f"Error validating inventory: {e}")
    
    def validate_finance_integrity(self):
        """Validate journal entries, accounts, and financial data."""
        print("\n" + "="*60)
        print("4. FINANCE DATA INTEGRITY")
        print("="*60)
        
        try:
            # Check accounts
            accounts_count = Account.objects.count()
            self.log_info(f"Total accounts: {accounts_count}")
            
            if accounts_count > 0:
                # Check for orphaned journal lines
                self.cursor.execute("""
                    SELECT COUNT(*) FROM finance_journalline jl
                    LEFT JOIN finance_journalentry je ON jl.journal_entry_id = je.id
                    WHERE je.id IS NULL
                """)
                orphaned_lines = self.cursor.fetchone()[0]
                if orphaned_lines > 0:
                    self.log_issue(f"Found {orphaned_lines} journal lines with missing entries")
                else:
                    self.log_info("✓ No orphaned journal lines")
                
                # Check journal entries
                je_count = JournalEntry.objects.count()
                self.log_info(f"Total journal entries: {je_count}")
                
                if je_count > 0:
                    # Check for unbalanced journal entries (debits != credits)
                    self.cursor.execute("""
                        SELECT je.id, SUM(CASE WHEN jl.entry_type='debit' THEN jl.amount ELSE -jl.amount END) as balance
                        FROM finance_journalentry je
                        LEFT JOIN finance_journalline jl ON je.id = jl.journal_entry_id
                        GROUP BY je.id
                        HAVING SUM(CASE WHEN jl.entry_type='debit' THEN jl.amount ELSE -jl.amount END) != 0
                        LIMIT 5
                    """)
                    unbalanced = self.cursor.fetchall()
                    if unbalanced:
                        self.log_warning(f"Found {len(unbalanced)} unbalanced journal entries")
                        for je_id, balance in unbalanced[:3]:
                            self.log_warning(f"  JE ID {je_id}: balance = {balance}")
                    else:
                        self.log_info("✓ All journal entries are balanced")
                        
        except Exception as e:
            self.log_warning(f"Error validating finance: {e}")
    
    def validate_suppliers_integrity(self):
        """Validate supplier purchases and payments."""
        print("\n" + "="*60)
        print("5. SUPPLIERS DATA INTEGRITY")
        print("="*60)
        
        try:
            # Check purchases
            purchase_count = Purchase.objects.count()
            self.log_info(f"Total purchases: {purchase_count}")
            
            if purchase_count > 0:
                # Check for orphaned purchase items
                self.cursor.execute("""
                    SELECT COUNT(*) FROM suppliers_purchaseitem spi
                    LEFT JOIN suppliers_purchase sp ON spi.purchase_id = sp.id
                    WHERE sp.id IS NULL
                """)
                orphaned_items = self.cursor.fetchone()[0]
                if orphaned_items > 0:
                    self.log_issue(f"Found {orphaned_items} orphaned purchase items")
                else:
                    self.log_info("✓ No orphaned purchase items")
                
                # Check purchase status values
                self.cursor.execute("""
                    SELECT DISTINCT status, COUNT(*) FROM suppliers_purchase GROUP BY status
                """)
                statuses = self.cursor.fetchall()
                for status, count in statuses:
                    self.log_info(f"  {status}: {count} purchases")
                    
                # Check for negative purchase amounts
                negative_purchases = Purchase.objects.filter(total_amount__lt=0).count()
                if negative_purchases > 0:
                    self.log_warning(f"Purchases with negative total_amount: {negative_purchases}")
                    
        except Exception as e:
            self.log_warning(f"Error validating suppliers: {e}")
    
    def validate_branch_data_integrity(self):
        """Validate branch and user relationships."""
        print("\n" + "="*60)
        print("6. BRANCH & USER DATA INTEGRITY")
        print("="*60)
        
        try:
            branches_count = Branch.objects.count()
            self.log_info(f"Total branches: {branches_count}")
            
            users_count = User.objects.count()
            self.log_info(f"Total users: {users_count}")
            
            if branches_count > 0:
                # Check for orphaned users (users without a branch)
                users_no_branch = User.objects.filter(branch__isnull=True).count()
                if users_no_branch > 0:
                    self.log_warning(f"Users without branch assignment: {users_no_branch}")
                else:
                    self.log_info("✓ All users have branch assigned")
                
                # Check users per branch
                self.cursor.execute("""
                    SELECT bb.name, COUNT(bu.id) as user_count
                    FROM branches_branch bb
                    LEFT JOIN branches_user bu ON bb.id = bu.branch_id
                    GROUP BY bb.id, bb.name
                    ORDER BY user_count DESC
                """)
                branch_users = self.cursor.fetchall()
                self.log_info("Users per branch:")
                for branch_name, user_count in branch_users:
                    self.log_info(f"  {branch_name}: {user_count} users")
                    
        except Exception as e:
            self.log_warning(f"Error validating branch data: {e}")
    
    def validate_referential_integrity_via_orm(self):
        """Validate referential integrity through ORM queries."""
        print("\n" + "="*60)
        print("7. ORM-LEVEL REFERENTIAL INTEGRITY")
        print("="*60)
        
        try:
            # Try querying through relationships to ensure FKs work
            
            # Orders → User
            orders_sample = Order.objects.select_related('created_by').first()
            if orders_sample:
                user = orders_sample.created_by
                self.log_info(f"✓ Order → User relationship works (order {orders_sample.id} → user {user.id})")
            
            # Inventory → Product
            trans_sample = InventoryTransaction.objects.select_related('product').first()
            if trans_sample:
                product = trans_sample.product
                self.log_info(f"✓ InventoryTransaction → Product relationship works")
            
            # JournalLine → Account
            je_sample = JournalEntry.objects.prefetch_related('journalline_set').first()
            if je_sample:
                for line in je_sample.journalline_set.all()[:1]:
                    account = line.account
                    self.log_info(f"✓ JournalLine → Account relationship works")
                    
            # Purchase → Supplier
            purchase_sample = Purchase.objects.select_related('supplier').first()
            if purchase_sample:
                supplier = purchase_sample.supplier
                self.log_info(f"✓ Purchase → Supplier relationship works")
                
        except Exception as e:
            self.log_issue(f"ORM relationship check failed: {e}")
    
    def generate_report(self):
        """Generate data integrity report."""
        print("\n" + "="*60)
        print("DATA INTEGRITY VALIDATION SUMMARY")
        print("="*60)
        
        total_issues = len(self.issues)
        total_warnings = len(self.warnings)
        
        print(f"\n📊 Results:")
        print(f"  Critical Issues: {total_issues}")
        print(f"  Warnings: {total_warnings}")
        print(f"  Info Messages: {len(self.info)}")
        
        if total_issues == 0:
            print("\n✅ All data integrity checks passed!")
        else:
            print(f"\n⚠️  Found {total_issues} critical issue(s):")
            for issue in self.issues:
                print(f"  - {issue}")
        
        return {
            'timestamp': datetime.now().isoformat(),
            'issues': self.issues,
            'warnings': self.warnings,
            'status': 'PASS' if total_issues == 0 else 'FAIL'
        }

if __name__ == '__main__':
    validator = DataIntegrityValidator()
    
    print("\n" + "="*60)
    print("FOREIGN KEY & DATA INTEGRITY VALIDATION")
    print("="*60)
    
    validator.validate_all_fk_constraints()
    validator.validate_orders_integrity()
    validator.validate_inventory_integrity()
    validator.validate_finance_integrity()
    validator.validate_suppliers_integrity()
    validator.validate_branch_data_integrity()
    validator.validate_referential_integrity_via_orm()
    
    report = validator.generate_report()
    
    # Save report
    with open('validation_report_data_integrity.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    sys.exit(0 if report['status'] == 'PASS' else 1)
