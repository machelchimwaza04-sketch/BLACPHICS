"""
Performance Testing Suite for BLACPHICS E-Commerce System
Tests API endpoints, database performance, and concurrent operations.
"""

import os
import sys
import time
import json
import psutil
import threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

# Django setup
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Blacphics.settings')

import django
django.setup()

from django.test import Client
from django.db import connection
from django.core.management import call_command
from django.conf import settings

# Models
from orders.models import Order, OrderItem, Payment
from products.models import Product, ProductVariant
from customers.models import Customer
from branches.models import Branch
from finance.models import DailyPLSnapshot

class PerformanceTestSuite:
    """Comprehensive performance testing suite for the e-commerce system."""

    def __init__(self):
        self.client = Client()
        self.results = {}
        self.test_data = {}
        # Allow testserver for testing
        from django.conf import settings
        if 'testserver' not in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS.append('testserver')

    def log(self, message):
        """Log with timestamp."""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {message}")

    def measure_memory_usage(self):
        """Get current memory usage in MB."""
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024

    def time_operation(self, operation_name, operation_func, *args, **kwargs):
        """Time an operation and record results."""
        start_time = time.time()
        start_memory = self.measure_memory_usage()

        try:
            result = operation_func(*args, **kwargs)
            success = True
        except Exception as e:
            result = str(e)
            success = False

        end_time = time.time()
        end_memory = self.measure_memory_usage()

        duration = end_time - start_time
        memory_delta = end_memory - start_memory

        self.results[operation_name] = {
            'duration': duration,
            'memory_delta': memory_delta,
            'success': success,
            'result': result,
            'timestamp': datetime.now().isoformat()
        }

        status = "✓" if success else "✗"
        self.log(f"{status} {operation_name}: {duration:.3f}s, {memory_delta:+.1f}MB")

        return result if success else None

    def setup_test_data(self):
        """Create test data for performance testing."""
        self.log("Setting up test data...")

        # Create test branch
        branch = Branch.objects.create(
            name="Performance Test Branch",
            address="123 Test St",
            phone="555-0123",
            manager_email="manager@test.com"
        )
        self.test_data['branch'] = branch

        # Create customers
        customers = []
        for i in range(100):
            customer = Customer.objects.create(
                name=f"Test Customer {i}",
                phone=f"555-{1000+i:04d}",
                email=f"customer{i}@test.com",
                branch=branch
            )
            customers.append(customer)
        self.test_data['customers'] = customers

        # Create products and variants
        products = []
        variants = []
        for i in range(50):
            product = Product.objects.create(
                name=f"Test Product {i}",
                description=f"Description for product {i}",
                branch=branch,
                base_price=10.00 + i
            )
            products.append(product)

            # Create variants for each product
            for size in ['S', 'M', 'L', 'XL']:
                variant = ProductVariant.objects.create(
                    product=product,
                    size=size,
                    stock_quantity=100,
                    price_modifier=0.00
                )
                variants.append(variant)

        self.test_data['products'] = products
        self.test_data['variants'] = variants

        self.log(f"Created: 1 branch, {len(customers)} customers, {len(products)} products, {len(variants)} variants")
        return True

    def cleanup_test_data(self):
        """Clean up test data."""
        self.log("Cleaning up test data...")
        try:
            Branch.objects.filter(name="Performance Test Branch").delete()
        except:
            pass

    def ensure_test_data(self):
        """Ensure we have test data, either by creating or using existing."""
        try:
            # Try to use existing data first
            branch = Branch.objects.first()
            if branch:
                customers = list(Customer.objects.filter(branch=branch)[:10])
                products = list(Product.objects.filter(branch=branch)[:5])
                variants = []
                for product in products:
                    variants.extend(list(ProductVariant.objects.filter(product=product)[:4]))

                if customers and products and variants:
                    self.test_data = {
                        'branch': branch,
                        'customers': customers,
                        'products': products,
                        'variants': variants
                    }
                    self.log("Using existing test data")
                    return True

            # If no existing data, create it
            return self.setup_test_data()
        except Exception as e:
            self.log(f"Failed to setup test data: {e}")
            return False

    def test_api_endpoints(self):
        """Test API endpoint performance."""
        self.log("Testing API endpoints...")

        branch = self.test_data['branch']

        # Test product listing
        self.time_operation(
            "API: List Products",
            lambda: self.client.get(f'/api/products/?branch={branch.id}')
        )

        # Test customer listing
        self.time_operation(
            "API: List Customers",
            lambda: self.client.get(f'/api/customers/?branch={branch.id}')
        )

        # Test order creation
        customer = self.test_data['customers'][0]
        variant = self.test_data['variants'][0]

        order_data = {
            'customer': customer.id,
            'branch': branch.id,
            'items': [{
                'variant': variant.id,
                'quantity': 1,
                'unit_price': float(variant.product.base_price)
            }],
            'payments': [{
                'amount': float(variant.product.base_price),
                'method': 'cash'
            }]
        }

        self.time_operation(
            "API: Create Order",
            lambda: self.client.post(
                '/api/orders/',
                data=json.dumps(order_data),
                content_type='application/json'
            )
        )

    def test_database_queries(self):
        """Test database query performance."""
        self.log("Testing database queries...")

        branch = self.test_data['branch']

        # Test complex order query with joins
        def complex_order_query():
            return list(Order.objects.filter(
                branch=branch
            ).select_related(
                'customer'
            ).prefetch_related(
                'items__variant__product',
                'payments'
            )[:10])

        self.time_operation("DB: Complex Order Query", complex_order_query)

        # Test product stock query
        def stock_query():
            return list(ProductVariant.objects.filter(
                product__branch=branch,
                stock_quantity__gt=0
            ).select_related('product'))

        self.time_operation("DB: Stock Availability Query", stock_query)

        # Test financial report query
        def financial_query():
            # Simulate P&L calculation
            orders = Order.objects.filter(
                branch=branch,
                created_at__gte=datetime.now() - timedelta(days=30)
            ).select_related('customer')

            total_revenue = sum(
                sum(item.quantity * item.unit_price for item in order.items.all())
                for order in orders
            )
            return total_revenue

        self.time_operation("DB: Financial Report Query", financial_query)

    def test_concurrent_operations(self, num_threads=10):
        """Test concurrent order creation."""
        self.log(f"Testing concurrent operations ({num_threads} threads)...")

        branch = self.test_data['branch']
        customers = self.test_data['customers'][:num_threads]
        variants = self.test_data['variants'][:num_threads]

        def create_order_thread(customer_idx):
            """Create an order in a thread."""
            customer = customers[customer_idx % len(customers)]
            variant = variants[customer_idx % len(variants)]

            order_data = {
                'customer': customer.id,
                'branch': branch.id,
                'items': [{
                    'variant': variant.id,
                    'quantity': 1,
                    'unit_price': float(variant.product.base_price)
                }],
                'payments': [{
                    'amount': float(variant.product.base_price),
                    'method': 'cash'
                }]
            }

            response = self.client.post(
                '/api/orders/',
                data=json.dumps(order_data),
                content_type='application/json'
            )
            return response.status_code == 201

        # Run concurrent operations
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_order_thread, i) for i in range(num_threads)]
            results = [future.result() for future in as_completed(futures)]

        duration = time.time() - start_time
        success_rate = sum(results) / len(results) * 100

        self.results['Concurrent Order Creation'] = {
            'duration': duration,
            'success_rate': success_rate,
            'threads': num_threads,
            'timestamp': datetime.now().isoformat()
        }

        self.log(f"✓ Concurrent Orders: {duration:.3f}s, {success_rate:.1f}% success rate")

    def test_stock_concurrency(self, num_threads=20):
        """Test stock management under concurrent load."""
        self.log(f"Testing stock concurrency ({num_threads} threads)...")

        branch = self.test_data['branch']
        variant = self.test_data['variants'][0]
        customer = self.test_data['customers'][0]

        # Ensure sufficient stock
        variant.stock_quantity = num_threads * 2
        variant.save()

        def order_same_variant(customer_idx):
            """Try to order the same variant concurrently."""
            order_data = {
                'customer': customer.id,
                'branch': branch.id,
                'items': [{
                    'variant': variant.id,
                    'quantity': 1,
                    'unit_price': float(variant.product.base_price)
                }],
                'payments': [{
                    'amount': float(variant.product.base_price),
                    'method': 'cash'
                }]
            }

            response = self.client.post(
                '/api/orders/',
                data=json.dumps(order_data),
                content_type='application/json'
            )
            return response.status_code

        # Run concurrent stock operations
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(order_same_variant, i) for i in range(num_threads)]
            status_codes = [future.result() for future in as_completed(futures)]

        duration = time.time() - start_time
        success_count = sum(1 for code in status_codes if code == 201)
        conflict_count = sum(1 for code in status_codes if code == 409)  # Assuming 409 for stock conflicts

        final_stock = ProductVariant.objects.get(id=variant.id).stock_quantity

        self.results['Stock Concurrency Test'] = {
            'duration': duration,
            'threads': num_threads,
            'successful_orders': success_count,
            'stock_conflicts': conflict_count,
            'initial_stock': num_threads * 2,
            'final_stock': final_stock,
            'timestamp': datetime.now().isoformat()
        }

        self.log(f"✓ Stock Concurrency: {duration:.3f}s, {success_count}/{num_threads} successful, final stock: {final_stock}")

    def test_financial_reporting(self):
        """Test financial report generation performance."""
        self.log("Testing financial reporting...")

        branch = self.test_data['branch']

        # Create some historical orders for reporting
        customer = self.test_data['customers'][0]
        variants = self.test_data['variants'][:5]

        for i in range(20):  # Create 20 orders
            order = Order.objects.create(
                customer=customer,
                branch=branch,
                status='completed'
            )

            for variant in variants:
                OrderItem.objects.create(
                    order=order,
                    variant=variant,
                    quantity=1,
                    unit_price=variant.product.base_price
                )

            Payment.objects.create(
                order=order,
                amount=sum(v.product.base_price for v in variants),
                method='cash'
            )

        # Test P&L report generation
        def generate_pl_report():
            # Simulate the P&L calculation logic
            orders = Order.objects.filter(
                branch=branch,
                created_at__gte=datetime.now() - timedelta(days=30)
            ).select_related('customer')

            revenue = 0
            costs = 0

            for order in orders:
                order_revenue = sum(
                    item.quantity * item.unit_price
                    for item in order.items.all()
                )
                revenue += order_revenue

                # Simulate cost calculation (assume 60% of revenue is cost)
                costs += order_revenue * 0.6

            return {
                'revenue': revenue,
                'costs': costs,
                'profit': revenue - costs
            }

        self.time_operation("Financial: P&L Report Generation", generate_pl_report)

    def generate_report(self):
        """Generate comprehensive performance report."""
        self.log("Generating performance report...")

        report = {
            'test_run': {
                'timestamp': datetime.now().isoformat(),
                'database': settings.DATABASES['default']['ENGINE'],
                'django_version': django.VERSION,
                'python_version': sys.version
            },
            'system_info': {
                'cpu_count': os.cpu_count(),
                'memory_total': psutil.virtual_memory().total / 1024 / 1024 / 1024,  # GB
                'memory_available': psutil.virtual_memory().available / 1024 / 1024 / 1024  # GB
            },
            'results': self.results
        }

        # Save report to file
        report_file = f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        self.log(f"Report saved to: {report_file}")

        # Print summary
        print("\n" + "="*60)
        print("PERFORMANCE TEST SUMMARY")
        print("="*60)

        print(f"Database: {settings.DATABASES['default']['ENGINE'].split('.')[-1]}")
        print(f"Total Tests: {len(self.results)}")
        print(f"Memory Usage: {self.measure_memory_usage():.1f}MB")
        print()

        # Group results by category
        categories = {
            'API': [k for k in self.results.keys() if k.startswith('API:')],
            'Database': [k for k in self.results.keys() if k.startswith('DB:')],
            'Financial': [k for k in self.results.keys() if k.startswith('Financial:')],
            'Concurrent': [k for k in self.results.keys() if 'Concurrent' in k or 'Stock' in k]
        }

        for category, tests in categories.items():
            if tests:
                print(f"{category} Tests:")
                for test in tests:
                    result = self.results[test]
                    status = "✓" if result.get('success', True) else "✗"
                    duration = result['duration']
                    print(f"  {status} {test}: {duration:.3f}s")
                print()

        return report

    def run_full_test_suite(self):
        """Run the complete performance test suite."""
        self.log("Starting BLACPHICS Performance Test Suite")
        self.log("="*50)

        try:
            # Setup
            if not self.ensure_test_data():
                self.log("Failed to setup test data, skipping tests")
                return

            # API Tests
            self.test_api_endpoints()

            # Database Tests
            self.test_database_queries()

            # Concurrent Tests
            self.test_concurrent_operations(num_threads=10)
            self.test_stock_concurrency(num_threads=15)

            # Financial Tests
            self.test_financial_reporting()

            # Generate Report
            report = self.generate_report()

        finally:
            # Cleanup
            self.time_operation("Cleanup: Test Data Removal", self.cleanup_test_data)

        self.log("Performance testing completed!")
        return report


if __name__ == '__main__':
    suite = PerformanceTestSuite()
    suite.run_full_test_suite()
