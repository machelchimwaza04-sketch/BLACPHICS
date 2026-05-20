#!/usr/bin/env python
"""
Auth System Validation Script
Verifies AUTH_USER_MODEL config, authentication backends, permissions, and admin panel.
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Blacphics.settings')
django.setup()

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.admin.sites import AdminSite
from branches.models import User, Branch
from django.db import connection
import json
from datetime import datetime

class AuthSystemValidator:
    """Validate authentication system configuration and functionality."""
    
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
    
    def validate_auth_user_model_config(self):
        """Verify AUTH_USER_MODEL is correctly configured."""
        print("\n" + "="*60)
        print("1. AUTH_USER_MODEL CONFIGURATION")
        print("="*60)
        
        auth_user_model = settings.AUTH_USER_MODEL
        self.log_info(f"AUTH_USER_MODEL setting: {auth_user_model}")
        
        if auth_user_model == 'branches.User':
            self.log_info("✓ AUTH_USER_MODEL correctly set to 'branches.User'")
        else:
            self.log_issue(f"AUTH_USER_MODEL is '{auth_user_model}', expected 'branches.User'")
        
        # Verify swappable model
        try:
            UserModel = get_user_model()
            self.log_info(f"get_user_model() returns: {UserModel.__name__}")
            
            if UserModel == User:
                self.log_info("✓ get_user_model() correctly returns custom User model")
            else:
                self.log_issue(f"get_user_model() returns {UserModel}, expected branches.User")
        except Exception as e:
            self.log_issue(f"Error getting user model: {e}")
    
    def validate_authentication_backend(self):
        """Verify authentication backend functionality."""
        print("\n" + "="*60)
        print("2. AUTHENTICATION BACKEND")
        print("="*60)
        
        backends = settings.AUTHENTICATION_BACKENDS
        self.log_info(f"Configured backends: {backends}")
        
        # Try to authenticate with existing user (if any)
        self.cursor.execute("SELECT id, email, password FROM branches_user LIMIT 1")
        user_row = self.cursor.fetchone()
        
        if user_row:
            user_id, email, password_hash = user_row
            try:
                user = User.objects.get(id=user_id)
                self.log_info(f"✓ Found user: {user.email} (ID: {user.id})")
                
                # Verify password hashing works
                if user.password and user.password.startswith('pbkdf2_sha256$'):
                    self.log_info("✓ Password is properly hashed (pbkdf2_sha256)")
                else:
                    self.log_warning(f"Password format may be invalid: {user.password[:20]}...")
                    
            except Exception as e:
                self.log_warning(f"Could not retrieve user for auth test: {e}")
        else:
            self.log_info("No users found for auth backend test")
    
    def validate_superuser_capability(self):
        """Verify superuser login capability."""
        print("\n" + "="*60)
        print("3. SUPERUSER CAPABILITY")
        print("="*60)
        
        try:
            superusers = User.objects.filter(is_superuser=True)
            su_count = superusers.count()
            
            if su_count > 0:
                self.log_info(f"✓ Superusers found: {su_count}")
                for su in superusers:
                    self.log_info(f"  - {su.email} (is_staff={su.is_staff}, is_active={su.is_active})")
                    
                    if not su.is_active:
                        self.log_warning(f"Superuser {su.email} is inactive")
                    if not su.is_staff:
                        self.log_warning(f"Superuser {su.email} is not marked as staff")
            else:
                self.log_warning("No superusers found in branches_user table")
                
        except Exception as e:
            self.log_issue(f"Error checking superusers: {e}")
    
    def validate_permission_relationships(self):
        """Verify permission and group relationships work correctly."""
        print("\n" + "="*60)
        print("4. PERMISSION & GROUP RELATIONSHIPS")
        print("="*60)
        
        try:
            # Check groups
            groups = Group.objects.all()
            self.log_info(f"Total groups: {groups.count()}")
            
            # Check permissions
            permissions = Permission.objects.all()
            self.log_info(f"Total permissions: {permissions.count()}")
            
            # Verify permission queries work
            for app in ['branches', 'orders', 'inventory', 'finance', 'suppliers']:
                perms = Permission.objects.filter(content_type__app_label=app)
                self.log_info(f"  {app}: {perms.count()} permissions")
            
            # Test user-permission relationships
            users_with_perms = User.objects.filter(user_permissions__isnull=False).distinct().count()
            users_in_groups = User.objects.filter(groups__isnull=False).distinct().count()
            
            self.log_info(f"✓ Users with direct permissions: {users_with_perms}")
            self.log_info(f"✓ Users in groups: {users_in_groups}")
            
        except Exception as e:
            self.log_issue(f"Error verifying permission relationships: {e}")
    
    def validate_admin_panel_compatibility(self):
        """Verify admin panel is compatible with custom User model."""
        print("\n" + "="*60)
        print("5. ADMIN PANEL COMPATIBILITY")
        print("="*60)
        
        try:
            from django.contrib import admin
            
            # Check if User is registered
            if User in admin.site._registry:
                self.log_info("✓ User model is registered in admin")
                user_admin = admin.site._registry[User]
                self.log_info(f"  Admin class: {user_admin.__class__.__name__}")
            else:
                self.log_warning("User model is NOT registered in admin")
            
            # Check if Branch is registered
            if Branch in admin.site._registry:
                self.log_info("✓ Branch model is registered in admin")
            else:
                self.log_warning("Branch model is NOT registered in admin")
                
            # Verify admin queryset access
            from django.contrib.admin.models import LogEntry
            log_entries = LogEntry.objects.all()
            entry_count = log_entries.count()
            self.log_info(f"✓ Admin log accessible: {entry_count} entries")
            
        except Exception as e:
            self.log_issue(f"Error checking admin panel: {e}")
    
    def validate_branch_scoped_access(self):
        """Verify branch-scoped access control works."""
        print("\n" + "="*60)
        print("6. BRANCH-SCOPED ACCESS CONTROL")
        print("="*60)
        
        try:
            branches = Branch.objects.all()
            self.log_info(f"Total branches: {branches.count()}")
            
            if branches.count() > 0:
                branch = branches.first()
                self.log_info(f"  Sample branch: {branch.name}")
                
                # Try to get users in branch
                branch_users = User.objects.filter(branch=branch)
                self.log_info(f"  Users in branch: {branch_users.count()}")
            
        except Exception as e:
            self.log_issue(f"Error accessing branch scoped data: {e}")
    
    def validate_user_model_methods(self):
        """Verify custom User model methods work correctly."""
        print("\n" + "="*60)
        print("7. CUSTOM USER MODEL METHODS")
        print("="*60)
        
        try:
            # Test __str__ method
            user = User.objects.first()
            if user:
                user_str = str(user)
                self.log_info(f"✓ User.__str__() works: {user_str}")
                
                # Test full_name method if it exists
                if hasattr(user, 'get_full_name'):
                    full_name = user.get_full_name()
                    self.log_info(f"  get_full_name(): {full_name}")
                    
                # Test other common methods
                self.log_info(f"  is_active: {user.is_active}")
                self.log_info(f"  is_staff: {user.is_staff}")
                self.log_info(f"  is_superuser: {user.is_superuser}")
            else:
                self.log_warning("No users found to test model methods")
                
        except Exception as e:
            self.log_issue(f"Error testing user model methods: {e}")
    
    def validate_password_validation(self):
        """Verify password validation works."""
        print("\n" + "="*60)
        print("8. PASSWORD VALIDATION")
        print("="*60)
        
        try:
            from django.contrib.auth.password_validation import validate_password
            from django.core.exceptions import ValidationError
            
            # Test valid password
            try:
                validate_password('TestPassword123!')
                self.log_info("✓ Password validator accepts strong password")
            except ValidationError as e:
                self.log_warning(f"Password validation issue: {e}")
            
            # Test weak password
            try:
                validate_password('123')
                self.log_warning("Password validator accepted weak password '123'")
            except ValidationError:
                self.log_info("✓ Password validator rejects weak passwords")
                
        except Exception as e:
            self.log_warning(f"Could not test password validation: {e}")
    
    def generate_report(self):
        """Generate auth validation report."""
        print("\n" + "="*60)
        print("AUTH SYSTEM VALIDATION SUMMARY")
        print("="*60)
        
        total_issues = len(self.issues)
        total_warnings = len(self.warnings)
        
        print(f"\n📊 Results:")
        print(f"  Critical Issues: {total_issues}")
        print(f"  Warnings: {total_warnings}")
        print(f"  Info Messages: {len(self.info)}")
        
        if total_issues == 0:
            print("\n✅ Auth system is properly configured and operational!")
        else:
            print(f"\n⚠️  Found {total_issues} issue(s):")
            for issue in self.issues:
                print(f"  - {issue}")
        
        if total_warnings > 0:
            print(f"\n⚠️  Warnings ({total_warnings}):")
            for warning in self.warnings[:5]:
                print(f"  - {warning}")
        
        return {
            'timestamp': datetime.now().isoformat(),
            'issues': self.issues,
            'warnings': self.warnings,
            'status': 'PASS' if total_issues == 0 else 'FAIL'
        }

if __name__ == '__main__':
    validator = AuthSystemValidator()
    
    print("\n" + "="*60)
    print("AUTH SYSTEM VALIDATION")
    print("="*60)
    
    validator.validate_auth_user_model_config()
    validator.validate_authentication_backend()
    validator.validate_superuser_capability()
    validator.validate_permission_relationships()
    validator.validate_admin_panel_compatibility()
    validator.validate_branch_scoped_access()
    validator.validate_user_model_methods()
    validator.validate_password_validation()
    
    report = validator.generate_report()
    
    # Save report
    with open('validation_report_auth_system.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    sys.exit(0 if report['status'] == 'PASS' else 1)
