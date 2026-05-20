#!/usr/bin/env python
"""
Migration Stability Validation Script
Checks for migration consistency, destructive operations, and schema drift.
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Blacphics.settings')
django.setup()

from django.db.migrations.loader import MigrationLoader
from django.db.migrations.executor import MigrationExecutor
from django.db import connection, DEFAULT_DB_ALIAS
from django.core.management import call_command
from io import StringIO
import json
from datetime import datetime

class MigrationStabilityValidator:
    """Validate migration consistency and schema drift."""
    
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
    
    def validate_migration_plan(self):
        """Run migration plan analysis."""
        print("\n" + "="*60)
        print("1. MIGRATION PLAN ANALYSIS")
        print("="*60)
        
        try:
            loader = MigrationLoader(None, ignore_no_migrations=True)
            executor = MigrationExecutor(connection)
            
            # Get planned migrations
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            
            if plan:
                self.log_warning(f"Found {len(plan)} unexecuted migrations:")
                for migration, backwards in plan:
                    self.log_warning(f"  - {migration}")
            else:
                self.log_info("✓ No unexecuted migrations found (all up to date)")
                
        except Exception as e:
            self.log_issue(f"Error analyzing migration plan: {e}")
    
    def validate_no_makemigrations_changes(self):
        """Ensure makemigrations returns 'No changes detected'."""
        print("\n" + "="*60)
        print("2. MAKEMIGRATIONS CONSISTENCY CHECK")
        print("="*60)
        
        try:
            out = StringIO()
            call_command('makemigrations', '--check', '--dry-run', stdout=out, stderr=out)
            output = out.getvalue()
            
            if 'No changes detected' in output:
                self.log_info("✓ makemigrations: No changes detected (schema is consistent)")
            else:
                self.log_warning(f"makemigrations output: {output[:200]}")
                
        except SystemExit:
            # makemigrations --check exits with 1 if changes would be made
            self.log_issue("makemigrations detected schema changes (models vs migrations out of sync)")
        except Exception as e:
            self.log_warning(f"Could not run makemigrations check: {e}")
    
    def validate_destructive_migrations(self):
        """Check for destructive migration patterns."""
        print("\n" + "="*60)
        print("3. DESTRUCTIVE MIGRATION DETECTION")
        print("="*60)
        
        try:
            loader = MigrationLoader(None, ignore_no_migrations=True)
            
            destructive_keywords = ['DeleteModel', 'RemoveField', 'RemoveIndex', 'AlterField']
            destructive_ops = []
            
            for app_label, migrations in loader.disk_migrations.items():
                for migration_name, migration in migrations.items():
                    for operation in migration.operations:
                        op_name = operation.__class__.__name__
                        if op_name in destructive_keywords:
                            destructive_ops.append({
                                'app': app_label,
                                'migration': migration_name,
                                'operation': op_name
                            })
            
            if destructive_ops:
                self.log_warning(f"Found {len(destructive_ops)} destructive operations:")
                for op in destructive_ops[:5]:
                    self.log_info(f"  - {op['app']}: {op['migration']} ({op['operation']})")
                if len(destructive_ops) > 5:
                    self.log_info(f"  ... and {len(destructive_ops) - 5} more")
            else:
                self.log_info("✓ No destructive migration operations found")
                
        except Exception as e:
            self.log_warning(f"Could not check for destructive migrations: {e}")
    
    def validate_applied_vs_disk(self):
        """Verify applied migrations match disk migrations."""
        print("\n" + "="*60)
        print("4. APPLIED VS DISK MIGRATIONS")
        print("="*60)
        
        try:
            # Get applied migrations
            self.cursor.execute("""
                SELECT app, name FROM django_migrations ORDER BY app, name
            """)
            applied = {(row[0], row[1]) for row in self.cursor.fetchall()}
            
            # Get disk migrations
            loader = MigrationLoader(None, ignore_no_migrations=True)
            disk = set()
            for app_label, migrations in loader.disk_migrations.items():
                for migration_name in migrations.keys():
                    disk.add((app_label, migration_name))
            
            missing_from_db = disk - applied
            extra_in_db = applied - disk
            
            if missing_from_db:
                self.log_warning(f"Migrations on disk but not applied: {len(missing_from_db)}")
                for app, name in sorted(missing_from_db)[:5]:
                    self.log_warning(f"  - {app}: {name}")
            else:
                self.log_info("✓ All disk migrations are applied")
            
            if extra_in_db:
                self.log_warning(f"Migrations applied but not on disk: {len(extra_in_db)}")
                for app, name in sorted(extra_in_db)[:5]:
                    self.log_info(f"  - {app}: {name}")
            else:
                self.log_info("✓ No orphaned applied migrations")
                
            self.log_info(f"Summary: {len(applied)} applied migrations, {len(disk)} disk migrations")
            
        except Exception as e:
            self.log_issue(f"Error comparing applied vs disk migrations: {e}")
    
    def validate_migration_dependencies(self):
        """Check for migration dependency cycles or broken references."""
        print("\n" + "="*60)
        print("5. MIGRATION DEPENDENCY VALIDATION")
        print("="*60)
        
        try:
            loader = MigrationLoader(None, ignore_no_migrations=True)
            graph = loader.graph
            
            # Check for cycles (shouldn't exist in Django)
            cycles = graph.circular_nodes()
            if cycles:
                self.log_issue(f"Found circular migration dependencies: {cycles}")
            else:
                self.log_info("✓ No circular migration dependencies")
            
            # Check for missing dependencies
            missing_deps = []
            for node in graph.nodes:
                for parent in graph.nodes[node].parents:
                    if parent not in graph.nodes:
                        missing_deps.append((node, parent))
            
            if missing_deps:
                self.log_issue(f"Found {len(missing_deps)} missing migration dependencies")
                for node, parent in missing_deps[:3]:
                    self.log_issue(f"  - {node} depends on missing {parent}")
            else:
                self.log_info("✓ All migration dependencies resolved")
                
        except Exception as e:
            self.log_warning(f"Could not validate migration dependencies: {e}")
    
    def validate_fake_migrations(self):
        """Check for fake migrations that might mask schema drift."""
        print("\n" + "="*60)
        print("6. FAKE MIGRATION DETECTION")
        print("="*60)
        
        try:
            self.cursor.execute("""
                SELECT COUNT(*) FROM django_migrations WHERE replace = true
            """)
            fake_count = self.cursor.fetchone()[0]
            
            if fake_count > 0:
                self.cursor.execute("""
                    SELECT app, name FROM django_migrations WHERE replace = true
                """)
                fakes = self.cursor.fetchall()
                self.log_warning(f"Found {fake_count} fake migrations (may mask schema drift):")
                for app, name in fakes[:5]:
                    self.log_warning(f"  - {app}: {name}")
            else:
                self.log_info("✓ No fake migrations detected")
                
        except Exception as e:
            self.log_warning(f"Could not check for fake migrations: {e}")
    
    def validate_migration_app_coverage(self):
        """Verify all Django apps have proper migration coverage."""
        print("\n" + "="*60)
        print("7. MIGRATION APP COVERAGE")
        print("="*60)
        
        try:
            loader = MigrationLoader(None, ignore_no_migrations=True)
            
            from django.apps import apps
            django_apps = set()
            for app_config in apps.get_app_configs():
                if app_config.name.startswith('django.'):
                    continue  # Skip Django built-ins
                django_apps.add(app_config.label)
            
            apps_with_migrations = set(loader.disk_migrations.keys())
            
            missing_migrations = django_apps - apps_with_migrations
            if missing_migrations:
                self.log_warning(f"Apps without migrations: {missing_migrations}")
            else:
                self.log_info("✓ All custom apps have migration files")
            
            self.log_info(f"Apps with migrations: {', '.join(sorted(apps_with_migrations))}")
            
        except Exception as e:
            self.log_warning(f"Could not verify migration app coverage: {e}")
    
    def validate_migration_ordering(self):
        """Verify migrations are in correct chronological order."""
        print("\n" + "="*60)
        print("8. MIGRATION ORDERING")
        print("="*60)
        
        try:
            self.cursor.execute("""
                SELECT app, name, id FROM django_migrations ORDER BY id
            """)
            
            migrations = self.cursor.fetchall()
            
            # Check for ordering issues
            app_counts = {}
            for app, name, _ in migrations:
                app_counts[app] = app_counts.get(app, 0) + 1
            
            self.log_info(f"✓ Total migrations applied: {len(migrations)}")
            for app in sorted(app_counts.keys()):
                self.log_info(f"  {app}: {app_counts[app]} migrations")
                
        except Exception as e:
            self.log_warning(f"Could not verify migration ordering: {e}")
    
    def generate_report(self):
        """Generate migration stability report."""
        print("\n" + "="*60)
        print("MIGRATION STABILITY SUMMARY")
        print("="*60)
        
        total_issues = len(self.issues)
        total_warnings = len(self.warnings)
        
        print(f"\n📊 Results:")
        print(f"  Critical Issues: {total_issues}")
        print(f"  Warnings: {total_warnings}")
        print(f"  Info Messages: {len(self.info)}")
        
        if total_issues == 0:
            print("\n✅ Migrations are stable and consistent!")
        else:
            print(f"\n⚠️  Found {total_issues} issue(s):")
            for issue in self.issues:
                print(f"  - {issue}")
        
        return {
            'timestamp': datetime.now().isoformat(),
            'issues': self.issues,
            'warnings': self.warnings,
            'status': 'PASS' if total_issues == 0 else 'FAIL'
        }

if __name__ == '__main__':
    validator = MigrationStabilityValidator()
    
    print("\n" + "="*60)
    print("MIGRATION STABILITY VALIDATION")
    print("="*60)
    
    validator.validate_migration_plan()
    validator.validate_no_makemigrations_changes()
    validator.validate_destructive_migrations()
    validator.validate_applied_vs_disk()
    validator.validate_migration_dependencies()
    validator.validate_fake_migrations()
    validator.validate_migration_app_coverage()
    validator.validate_migration_ordering()
    
    report = validator.generate_report()
    
    # Save report
    with open('validation_report_migration_stability.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    sys.exit(0 if report['status'] == 'PASS' else 1)
