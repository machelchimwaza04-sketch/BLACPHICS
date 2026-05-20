from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from branches.models import Branch

User = get_user_model()

class Command(BaseCommand):
    help = 'Create initial admin user and sample branch'

    def handle(self, *args, **options):
        # Create sample branch if it doesn't exist
        branch, created = Branch.objects.get_or_create(
            name='Main Branch',
            defaults={
                'city': 'Default City',
                'address': 'Default Address',
                'phone': '+1234567890',
                'email': 'main@blacphics.com'
            }
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created branch: {branch.name}')
            )

        # Create admin user if it doesn't exist
        if not User.objects.filter(username='admin').exists():
            admin = User.objects.create_user(
                username='admin',
                email='admin@blacphics.com',
                password='admin123!',
                first_name='System',
                last_name='Administrator',
                role='admin',
                is_staff=True,
                is_superuser=True
            )
            self.stdout.write(
                self.style.SUCCESS(f'Created admin user: {admin.username}')
            )
        else:
            self.stdout.write(
                self.style.WARNING('Admin user already exists')
            )

        # Create sample branch manager
        if not User.objects.filter(username='manager').exists():
            manager = User.objects.create_user(
                username='manager',
                email='manager@blacphics.com',
                password='manager123!',
                first_name='Branch',
                last_name='Manager',
                role='branch_manager',
                branch=branch
            )
            self.stdout.write(
                self.style.SUCCESS(f'Created branch manager: {manager.username}')
            )

        # Create sample cashier
        if not User.objects.filter(username='cashier').exists():
            cashier = User.objects.create_user(
                username='cashier',
                email='cashier@blacphics.com',
                password='cashier123!',
                first_name='Sample',
                last_name='Cashier',
                role='cashier',
                branch=branch
            )
            self.stdout.write(
                self.style.SUCCESS(f'Created cashier: {cashier.username}')
            )