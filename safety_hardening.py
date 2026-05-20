#!/usr/bin/env python
"""
Safety Hardening & Backup Script
Creates PostgreSQL backups, schema snapshots, migration graphs, and audit reports.
"""

import os
import sys
import django
import subprocess
import json
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Blacphics.settings')
django.setup()

from django.db import connection
from django.conf import settings
from django.db.migrations.loader import MigrationLoader
from django.apps import apps

def get_db_config():
    """Get database configuration."""
    db_config = settings.DATABASES['default']
    return {
        'engine': db_config.get('ENGINE', ''),
        'name': db_config.get('NAME', ''),
        'user': db_config.get('USER', ''),
        'password': db_config.get('PASSWORD', ''),
        'host': db_config.get('HOST', 'localhost'),
        'port': db_config.get('PORT', 5432),
    }

def create_postgresql_backup():
    """Create PostgreSQL database backup."""
    print("\n" + "="*60)
    print("CREATING POSTGRESQL BACKUP")
    print("="*60)
    
    try:
        config = get_db_config()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"backup_db_{timestamp}.sql"
        
        # Construct pg_dump command
        env = os.environ.copy()
        if config.get('password'):
            env['PGPASSWORD'] = config['password']
        
        cmd = [
            'pg_dump',
            '--username', config['user'],
            '--host', config['host'],
            '--port', str(config['port']),
            '--format', 'plain',
            '--compress', '9',
            '--file', backup_file + '.gz',
            config['name']
        ]
        
        print(f"Creating backup: {backup_file}.gz")
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            file_size = os.path.getsize(backup_file + '.gz') / (1024 * 1024)  # MB
            print(f"✓ Backup created successfully: {file_size:.2f} MB")
            return backup_file + '.gz'
        else:
            print(f"❌ Backup failed: {result.stderr}")
            return None
            
    except FileNotFoundError:
        print("⚠️  pg_dump not found. Make sure PostgreSQL is installed.")
        return None
    except Exception as e:
        print(f"❌ Error creating backup: {e}")
        return None

def generate_schema_snapshot():
    """Generate complete schema snapshot."""
    print("\n" + "="*60)
    print("GENERATING SCHEMA SNAPSHOT")
    print("="*60)
    
    cursor = connection.cursor()
    snapshot = {
        'timestamp': datetime.now().isoformat(),
        'tables': [],
        'indexes': [],
        'constraints': [],
        'sequences': [],
    }
    
    try:
        # Get all tables
        cursor.execute("""
            SELECT tablename FROM pg_catalog.pg_tables 
            WHERE schemaname = 'public' ORDER BY tablename
        """)
        tables = [r[0] for r in cursor.fetchall()]
        snapshot['tables'] = tables
        print(f"✓ Found {len(tables)} tables")
        
        # Get all indexes
        cursor.execute("""
            SELECT schemaname, tablename, indexname 
            FROM pg_indexes WHERE schemaname = 'public' 
            ORDER BY tablename, indexname
        """)
        indexes = [{'schema': r[0], 'table': r[1], 'index': r[2]} for r in cursor.fetchall()]
        snapshot['indexes'] = indexes
        print(f"✓ Found {len(indexes)} indexes")
        
        # Get all constraints
        cursor.execute("""
            SELECT tc.table_name, tc.constraint_name, tc.constraint_type
            FROM information_schema.table_constraints tc
            WHERE tc.table_schema = 'public'
            ORDER BY tc.table_name, tc.constraint_name
        """)
        constraints = [{'table': r[0], 'name': r[1], 'type': r[2]} for r in cursor.fetchall()]
        snapshot['constraints'] = constraints
        print(f"✓ Found {len(constraints)} constraints")
        
        # Get all sequences
        cursor.execute("""
            SELECT sequence_schema, sequence_name 
            FROM information_schema.sequences 
            WHERE sequence_schema = 'public'
            ORDER BY sequence_name
        """)
        sequences = [{'schema': r[0], 'name': r[1]} for r in cursor.fetchall()]
        snapshot['sequences'] = sequences
        print(f"✓ Found {len(sequences)} sequences")
        
    except Exception as e:
        print(f"❌ Error generating schema snapshot: {e}")
    
    # Save snapshot
    snapshot_file = f"schema_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(snapshot_file, 'w') as f:
        json.dump(snapshot, f, indent=2)
    print(f"✓ Schema snapshot saved to {snapshot_file}")
    
    return snapshot_file

def generate_migration_dependency_graph():
    """Generate migration dependency graph."""
    print("\n" + "="*60)
    print("GENERATING MIGRATION DEPENDENCY GRAPH")
    print("="*60)
    
    try:
        loader = MigrationLoader(None, ignore_no_migrations=True)
        
        graph_data = {
            'timestamp': datetime.now().isoformat(),
            'migrations': [],
            'dependencies': [],
        }
        
        # Build migration node list
        migration_list = []
        for app_label, migrations in loader.disk_migrations.items():
            for migration_name in migrations.keys():
                migration_list.append((app_label, migration_name))
        
        for app_label, migration_name in migration_list:
            graph_data['migrations'].append({
                'app': app_label,
                'name': migration_name
            })
        
        print(f"✓ Found {len(migration_list)} migrations")
        
        # Build dependency list (simplified)
        for app_label, migrations in loader.disk_migrations.items():
            for migration_name, migration_obj in migrations.items():
                for dep in getattr(migration_obj, 'dependencies', []):
                    graph_data['dependencies'].append({
                        'from': f"{app_label}:{migration_name}",
                        'to': f"{dep[0]}:{dep[1]}"
                    })
        
        print(f"✓ Found {len(graph_data['dependencies'])} dependencies")
        
    except Exception as e:
        print(f"⚠️  Could not generate full migration graph: {e}")
        graph_data = {
            'timestamp': datetime.now().isoformat(),
            'migrations': [],
            'dependencies': [],
            'error': str(e)
        }
    
    # Save graph
    graph_file = f"migration_graph_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(graph_file, 'w') as f:
        json.dump(graph_data, f, indent=2)
    print(f"✓ Migration graph saved to {graph_file}")
    
    return graph_file

def generate_integrity_audit_report():
    """Generate comprehensive integrity audit report."""
    print("\n" + "="*60)
    print("GENERATING INTEGRITY AUDIT REPORT")
    print("="*60)
    
    cursor = connection.cursor()
    audit_report = {
        'timestamp': datetime.now().isoformat(),
        'system_status': 'UNKNOWN',
        'checks': {},
    }
    
    try:
        # Check 1: Database connections
        try:
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            audit_report['checks']['database_version'] = {
                'status': 'OK',
                'value': version[:50] + '...' if len(version) > 50 else version
            }
            print("✓ Database version check")
        except Exception as e:
            audit_report['checks']['database_version'] = {'status': 'FAIL', 'error': str(e)}
        
        # Check 2: Table integrity
        try:
            cursor.execute("SELECT COUNT(*) FROM pg_catalog.pg_tables WHERE schemaname='public'")
            table_count = cursor.fetchone()[0]
            audit_report['checks']['table_count'] = {
                'status': 'OK',
                'value': table_count
            }
            print(f"✓ Table count: {table_count}")
        except Exception as e:
            audit_report['checks']['table_count'] = {'status': 'FAIL', 'error': str(e)}
        
        # Check 3: Foreign key count
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM pg_constraint 
                WHERE contype = 'f'
            """)
            fk_count = cursor.fetchone()[0]
            audit_report['checks']['foreign_key_count'] = {
                'status': 'OK',
                'value': fk_count
            }
            print(f"✓ Foreign key count: {fk_count}")
        except Exception as e:
            audit_report['checks']['foreign_key_count'] = {'status': 'FAIL', 'error': str(e)}
        
        # Check 4: Migration count
        try:
            cursor.execute("SELECT COUNT(*) FROM django_migrations")
            migration_count = cursor.fetchone()[0]
            audit_report['checks']['migration_count'] = {
                'status': 'OK',
                'value': migration_count
            }
            print(f"✓ Migration count: {migration_count}")
        except Exception as e:
            audit_report['checks']['migration_count'] = {'status': 'FAIL', 'error': str(e)}
        
        # Check 5: Auth system
        try:
            cursor.execute("SELECT COUNT(*) FROM branches_user")
            branches_user_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM auth_user")
            auth_user_count = cursor.fetchone()[0]
            
            auth_status = 'OK' if branches_user_count > 0 else 'WARNING'
            audit_report['checks']['auth_system'] = {
                'status': auth_status,
                'branches_user': branches_user_count,
                'auth_user': auth_user_count
            }
            print(f"✓ Auth system check: branches_user={branches_user_count}, auth_user={auth_user_count}")
        except Exception as e:
            audit_report['checks']['auth_system'] = {'status': 'FAIL', 'error': str(e)}
        
        # Check 6: Data existence
        try:
            cursor.execute("SELECT COUNT(*) FROM branches_branch")
            branches = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM orders_order")
            orders = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM products_product")
            products = cursor.fetchone()[0]
            
            audit_report['checks']['data_summary'] = {
                'status': 'OK',
                'branches': branches,
                'orders': orders,
                'products': products
            }
            print(f"✓ Data summary: branches={branches}, orders={orders}, products={products}")
        except Exception as e:
            audit_report['checks']['data_summary'] = {'status': 'FAIL', 'error': str(e)}
        
        # Determine overall status
        failed_checks = [k for k, v in audit_report['checks'].items() if v.get('status') == 'FAIL']
        if not failed_checks:
            audit_report['system_status'] = 'HEALTHY'
        else:
            audit_report['system_status'] = 'WARNING'
        
    except Exception as e:
        audit_report['system_status'] = 'ERROR'
        audit_report['error'] = str(e)
    
    print(f"\n✓ System Status: {audit_report['system_status']}")
    
    # Save report
    report_file = f"integrity_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(audit_report, f, indent=2)
    print(f"✓ Audit report saved to {report_file}")
    
    return report_file

def document_patches_and_repairs():
    """Document manual patches requiring normalization."""
    print("\n" + "="*60)
    print("DOCUMENTING PATCHES & REPAIRS")
    print("="*60)
    
    patches = {
        'timestamp': datetime.now().isoformat(),
        'repairs_applied': [
            {
                'issue': 'Missing branches_user table',
                'repair': 'Created custom auth schema (branches_user, branches_user_groups, branches_user_user_permissions)',
                'applied_by': 'tmp_branch_repair.py',
                'date': 'Session repair',
                'requires_normalization': False,
                'notes': 'Foreign keys repointed from auth_user to branches_user for django_admin_log and orders_order'
            },
            {
                'issue': 'Foreign keys pointing to auth_user',
                'repair': 'Repointed FK constraints to branches_user',
                'applied_by': 'tmp_branch_repair.py',
                'date': 'Session repair',
                'requires_normalization': False,
                'notes': 'Affected tables: django_admin_log, orders_order'
            },
            {
                'issue': 'branches.0003 migration pending',
                'repair': 'Applied branches.0003_alter_user_options_alter_user_branch_and_more',
                'applied_by': 'manage.py migrate branches',
                'date': 'Session repair',
                'requires_normalization': False,
                'notes': 'Migration applied successfully after schema repair'
            }
        ],
        'ongoing_monitoring': [
            'Verify branches.User remains active custom auth model',
            'Monitor for any stale auth_user references',
            'Verify branch-scoped access controls work correctly',
            'Check for users without branch assignment'
        ]
    }
    
    # Save patches documentation
    patches_file = f"patches_documentation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(patches_file, 'w') as f:
        json.dump(patches, f, indent=2)
    
    print("\n✓ Patches & repairs documented:")
    for repair in patches['repairs_applied']:
        print(f"  - {repair['issue']}: {repair['repair']}")
    print(f"\n✓ Patches documentation saved to {patches_file}")
    
    return patches_file

if __name__ == '__main__':
    print("\n" + "="*60)
    print("SAFETY HARDENING & BACKUP")
    print("="*60)
    
    files_created = []
    
    # Create PostgreSQL backup
    backup_file = create_postgresql_backup()
    if backup_file:
        files_created.append(backup_file)
    
    # Generate schema snapshot
    snapshot_file = generate_schema_snapshot()
    files_created.append(snapshot_file)
    
    # Generate migration graph
    graph_file = generate_migration_dependency_graph()
    files_created.append(graph_file)
    
    # Generate integrity audit
    audit_file = generate_integrity_audit_report()
    files_created.append(audit_file)
    
    # Document patches
    patches_file = document_patches_and_repairs()
    files_created.append(patches_file)
    
    print("\n" + "="*60)
    print("SAFETY HARDENING COMPLETE")
    print("="*60)
    print(f"\n✓ Created {len(files_created)} backup/documentation files:")
    for f in files_created:
        print(f"  - {f}")
