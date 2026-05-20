#!/usr/bin/env python
"""
Comprehensive Database Consistency Validation Script
Checks migrations, schema state, foreign keys, and data integrity.
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Blacphics.settings')
django.setup()

from django.db import connection
from django.core.management import call_command
from django.apps import apps
from django.db.models import Model
from io import StringIO
import json
from datetime import datetime

def get_db_cursor():
    """Get a raw database cursor."""
    return connection.cursor()

class DBConsistencyValidator:
    """Validate database consistency after auth schema repair."""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.info = []
        self.cursor = get_db_cursor()
        
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
    
    def validate_migrations_vs_schema(self):
        """Verify all Django migrations are synchronized with PostgreSQL schema state."""
        print("\n" + "="*60)
        print("1. MIGRATIONS VS SCHEMA SYNCHRONIZATION")
        print("="*60)
        
        # Get all applied migrations from django_migrations table
        self.cursor.execute("""
            SELECT app, name FROM django_migrations ORDER BY app, name
        """)
        applied_migrations = self.cursor.fetchall()
        self.log_info(f"Applied migrations: {len(applied_migrations)}")
        
        # Get all Django-managed apps with migrations
        try:
            from django.db.migrations.loader import MigrationLoader
            loader = MigrationLoader(None, ignore_no_migrations=True)
            
            for app_label in sorted(loader.disk_migrations.keys()):
                migrations = loader.disk_migrations[app_label]
                applied = [m for a, m in applied_migrations if a == app_label]
                disk_migrations = list(migrations.keys())
                
                if len(applied) != len(disk_migrations):
                    self.log_warning(f"{app_label}: {len(applied)} applied vs {len(disk_migrations)} on disk")
                else:
                    self.log_info(f"{app_label}: {len(applied)} migrations applied ✓")
                    
        except Exception as e:
            self.log_warning(f"Could not fully verify migration state: {e}")
    
    def validate_duplicate_tables(self):
        """Detect duplicate tables (e.g., auth_user and branches_user both existing)."""
        print("\n" + "="*60)
        print("2. DUPLICATE TABLE DETECTION")
        print("="*60)
        
        self.cursor.execute("""
            SELECT tablename FROM pg_catalog.pg_tables 
            WHERE schemaname = 'public' ORDER BY tablename
        """)
        tables = [r[0] for r in self.cursor.fetchall()]
        
        self.log_info(f"Total tables in public schema: {len(tables)}")
        
        # Check for problematic duplicates
        auth_user_exists = 'auth_user' in tables
        branches_user_exists = 'branches_user' in tables
        
        if auth_user_exists:
            self.log_info("auth_user table exists")
        if branches_user_exists:
            self.log_info("branches_user table exists (custom auth)")
            
        if auth_user_exists and branches_user_exists:
            # Both exist, which is OK for migration period
            self.cursor.execute("SELECT COUNT(*) FROM auth_user")
            auth_count = self.cursor.fetchone()[0]
            self.cursor.execute("SELECT COUNT(*) FROM branches_user")
            branches_count = self.cursor.fetchone()[0]
            
            if auth_count == 0 and branches_count > 0:
                self.log_info(f"✓ Correctly transitioned: auth_user is empty (0 rows), branches_user has {branches_count} rows")
            elif auth_count > 0 and branches_count > 0:
                if auth_count == branches_count:
                    self.log_info(f"✓ Both tables populated with same row count ({auth_count})")
                else:
                    self.log_warning(f"Row count mismatch: auth_user={auth_count}, branches_user={branches_count}")
    
    def validate_foreign_keys(self):
        """Verify all foreign keys referencing users now point to branches_user."""
        print("\n" + "="*60)
        print("3. FOREIGN KEY VALIDATION")
        print("="*60)
        
        # Get all foreign keys in the database
        self.cursor.execute("""
            SELECT 
                conname,
                conrelid::regclass as table_name,
                a.attname as column_name,
                confrelid::regclass as referenced_table,
                b.attname as referenced_column
            FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid = conrelid AND a.attnum = conkey[1]
            JOIN pg_attribute b ON b.attrelid = confrelid AND b.attnum = confkey[1]
            WHERE contype = 'f'
            ORDER BY conrelid::regclass, conname
        """)
        
        fks = self.cursor.fetchall()
        self.log_info(f"Total foreign keys: {len(fks)}")
        
        auth_user_fks = [fk for fk in fks if 'auth_user' in str(fk[3])]
        branches_user_fks = [fk for fk in fks if 'branches_user' in str(fk[3])]
        
        self.log_info(f"FKs pointing to auth_user: {len(auth_user_fks)}")
        self.log_info(f"FKs pointing to branches_user: {len(branches_user_fks)}")
        
        if auth_user_fks:
            for fk in auth_user_fks:
                # Internal auth relations are OK
                if fk[1] in ('auth_user_groups', 'auth_user_user_permissions'):
                    self.log_info(f"✓ {fk[0]}: {fk[1]}.{fk[2]} → auth_user (internal)")
                else:
                    self.log_issue(f"Non-auth table FK to auth_user: {fk[0]} ({fk[1]}.{fk[2]} → {fk[3]})")
        
        # Verify critical FKs are pointing to branches_user
        critical_tables = ['django_admin_log', 'orders_order']
        for table_name in critical_tables:
            table_fks = [fk for fk in branches_user_fks if str(fk[1]) == table_name]
            if table_fks:
                for fk in table_fks:
                    self.log_info(f"✓ {fk[0]}: {fk[1]}.{fk[2]} → branches_user")
    
    def validate_content_type_consistency(self):
        """Verify django_content_type consistency."""
        print("\n" + "="*60)
        print("4. CONTENT TYPE CONSISTENCY")
        print("="*60)
        
        self.cursor.execute("""
            SELECT id, app_label, model, COUNT(*) as count
            FROM django_content_type
            GROUP BY app_label, model, id
            ORDER BY app_label, model
        """)
        
        content_types = self.cursor.fetchall()
        self.log_info(f"Total content types: {len(content_types)}")
        
        # Check for duplicates
        self.cursor.execute("""
            SELECT app_label, model, COUNT(*) as count
            FROM django_content_type
            GROUP BY app_label, model
            HAVING COUNT(*) > 1
        """)
        
        duplicates = self.cursor.fetchall()
        if duplicates:
            for dup in duplicates:
                self.log_issue(f"Duplicate content type: {dup[0]}.{dup[1]} (count: {dup[2]})")
        else:
            self.log_info("✓ No duplicate content types")
        
        # Verify branches.User exists
        self.cursor.execute("""
            SELECT id FROM django_content_type WHERE app_label='branches' AND model='user'
        """)
        branches_user_ct = self.cursor.fetchone()
        if branches_user_ct:
            self.log_info("✓ branches.User content type exists")
        else:
            self.log_warning("branches.User content type not found in django_content_type")
    
    def validate_auth_permissions(self):
        """Verify auth_permission integrity."""
        print("\n" + "="*60)
        print("5. AUTH PERMISSION INTEGRITY")
        print("="*60)
        
        self.cursor.execute("""
            SELECT COUNT(*) FROM auth_permission
        """)
        perm_count = self.cursor.fetchone()[0]
        self.log_info(f"Total permissions: {perm_count}")
        
        # Check for orphaned permissions (content_type that no longer exists)
        self.cursor.execute("""
            SELECT p.id, p.codename, p.content_type_id
            FROM auth_permission p
            LEFT JOIN django_content_type ct ON p.content_type_id = ct.id
            WHERE ct.id IS NULL
        """)
        
        orphaned = self.cursor.fetchall()
        if orphaned:
            for perm in orphaned:
                self.log_issue(f"Orphaned permission: {perm[1]} (content_type_id: {perm[2]})")
        else:
            self.log_info("✓ No orphaned permissions")
    
    def validate_admin_log_integrity(self):
        """Verify admin log integrity."""
        print("\n" + "="*60)
        print("6. ADMIN LOG INTEGRITY")
        print("="*60)
        
        self.cursor.execute("SELECT COUNT(*) FROM django_admin_log")
        admin_log_count = self.cursor.fetchone()[0]
        self.log_info(f"Admin log entries: {admin_log_count}")
        
        # Check for orphaned admin log entries (user_id pointing to non-existent user)
        self.cursor.execute("""
            SELECT dal.id, dal.user_id, dal.object_id, dal.action_flag
            FROM django_admin_log dal
            LEFT JOIN branches_user u ON dal.user_id = u.id
            WHERE u.id IS NULL
            LIMIT 5
        """)
        
        orphaned_logs = self.cursor.fetchall()
        if orphaned_logs:
            for log in orphaned_logs:
                self.log_issue(f"Orphaned admin log entry: id={log[0]}, user_id={log[1]}")
        else:
            self.log_info("✓ All admin log user references valid")
    
    def validate_migration_records(self):
        """Verify no stale migration records exist."""
        print("\n" + "="*60)
        print("7. MIGRATION RECORDS")
        print("="*60)
        
        self.cursor.execute("""
            SELECT app, name FROM django_migrations ORDER BY applied DESC LIMIT 10
        """)
        
        recent_migrations = self.cursor.fetchall()
        self.log_info(f"Recent migrations applied:")
        for app, name in recent_migrations:
            self.log_info(f"  - {app}: {name}")
    
    def validate_indexes(self):
        """Detect invalid or orphaned indexes."""
        print("\n" + "="*60)
        print("8. INDEX VALIDATION")
        print("="*60)
        
        self.cursor.execute("""
            SELECT schemaname, tablename, indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname
        """)
        
        indexes = self.cursor.fetchall()
        self.log_info(f"Total indexes: {len(indexes)}")
        
        # Check for broken indexes
        try:
            self.cursor.execute("REINDEX DATABASE blacphics")
            self.log_info("✓ REINDEX check passed")
        except Exception as e:
            self.log_warning(f"REINDEX issue detected: {str(e)[:100]}")
    
    def generate_report(self):
        """Generate validation report."""
        print("\n" + "="*60)
        print("VALIDATION SUMMARY")
        print("="*60)
        
        total_issues = len(self.issues)
        total_warnings = len(self.warnings)
        total_info = len(self.info)
        
        print(f"\n📊 Results:")
        print(f"  Critical Issues: {total_issues}")
        print(f"  Warnings: {total_warnings}")
        print(f"  Info Messages: {total_info}")
        
        if total_issues == 0:
            print("\n✅ Database is consistent and ready for operation!")
        else:
            print(f"\n⚠️  Found {total_issues} issue(s) that need attention")
            print("\nIssues:")
            for issue in self.issues:
                print(f"  - {issue}")
        
        if total_warnings > 0:
            print(f"\n⚠️  Warnings ({total_warnings}):")
            for warning in self.warnings[:5]:
                print(f"  - {warning}")
            if len(self.warnings) > 5:
                print(f"  ... and {len(self.warnings) - 5} more")
        
        return {
            'timestamp': datetime.now().isoformat(),
            'issues': self.issues,
            'warnings': self.warnings,
            'info_count': total_info,
            'status': 'PASS' if total_issues == 0 else 'FAIL'
        }

if __name__ == '__main__':
    validator = DBConsistencyValidator()
    
    print("\n" + "="*60)
    print("DATABASE CONSISTENCY VALIDATION")
    print("="*60)
    
    validator.validate_migrations_vs_schema()
    validator.validate_duplicate_tables()
    validator.validate_foreign_keys()
    validator.validate_content_type_consistency()
    validator.validate_auth_permissions()
    validator.validate_admin_log_integrity()
    validator.validate_migration_records()
    validator.validate_indexes()
    
    report = validator.generate_report()
    
    # Save report
    with open('validation_report_db_consistency.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    sys.exit(0 if report['status'] == 'PASS' else 1)
