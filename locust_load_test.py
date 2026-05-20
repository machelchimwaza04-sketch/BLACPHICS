#!/usr/bin/env python
"""
Locust Load Testing Script for BLACPHICS E-Commerce System
Simulates real user behavior with different user types and scenarios.
"""

import json
import random
from locust import HttpUser, task, between, tag
from locust.contrib.fasthttp import FastHttpUser

class EcommerceUser(FastHttpUser):
    """Base user class for e-commerce load testing."""

    wait_time = between(1, 3)  # Random wait between 1-3 seconds

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.branch_id = None
        self.customer_id = None
        self.auth_token = None

    def on_start(self):
        """Setup user session - simulate login/branch selection."""
        # Select a random branch (simulate multi-tenant behavior)
        self.branch_id = random.randint(1, 5)  # Assuming 5 branches

        # Simulate customer selection (80% returning customers, 20% new)
        if random.random() < 0.8:
            self.customer_id = random.randint(1, 100)  # Existing customer
        else:
            self.customer_id = None  # New customer

class BrowseUser(EcommerceUser):
    """User who browses products without purchasing."""

    weight = 60  # 60% of users are browsers

    @tag('browse')
    @task(5)
    def browse_products(self):
        """Browse product catalog."""
        params = {'branch': self.branch_id}
        if random.random() < 0.3:  # 30% add search
            params['search'] = random.choice(['shirt', 'pants', 'dress', 'shoes'])

        with self.client.get("/api/products/", params=params, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Browse products failed: {response.status_code}")

    @tag('browse')
    @task(2)
    def view_product_details(self):
        """View detailed product information."""
        product_id = random.randint(1, 50)  # Random product
        with self.client.get(f"/api/products/{product_id}/", catch_response=True) as response:
            if response.status_code in [200, 404]:  # 404 is acceptable for random IDs
                response.success()
            else:
                response.failure(f"Product details failed: {response.status_code}")

    @tag('browse')
    @task(1)
    def check_stock_alerts(self):
        """Check low stock alerts (admin/managers only)."""
        with self.client.get(f"/api/products/alerts/?branch={self.branch_id}", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Stock alerts failed: {response.status_code}")

class CustomerUser(EcommerceUser):
    """User who makes purchases."""

    weight = 35  # 35% of users are customers

    @tag('purchase')
    @task(3)
    def create_order(self):
        """Create a new order."""
        # Select random products and variants
        num_items = random.randint(1, 5)
        items = []

        for _ in range(num_items):
            variant_id = random.randint(1, 200)  # Random variant
            quantity = random.randint(1, 3)
            unit_price = round(random.uniform(10, 100), 2)

            items.append({
                'variant': variant_id,
                'quantity': quantity,
                'unit_price': unit_price
            })

        # Calculate total for payment
        total_amount = sum(item['quantity'] * item['unit_price'] for item in items)

        order_data = {
            'customer': self.customer_id or random.randint(1, 100),
            'branch': self.branch_id,
            'items': items,
            'payments': [{
                'amount': total_amount,
                'method': random.choice(['cash', 'card', 'transfer'])
            }]
        }

        with self.client.post(
            "/api/orders/",
            json=order_data,
            headers={'Content-Type': 'application/json'},
            catch_response=True
        ) as response:
            if response.status_code == 201:
                response.success()
                # Store order ID for follow-up tasks
                try:
                    order_response = response.json()
                    self.last_order_id = order_response.get('id')
                except:
                    pass
            elif response.status_code == 400:
                # Stock issues or validation errors are expected
                response.success()
            else:
                response.failure(f"Order creation failed: {response.status_code}")

    @tag('purchase')
    @task(1)
    def add_payment_to_order(self):
        """Add payment to existing order."""
        if hasattr(self, 'last_order_id') and self.last_order_id:
            payment_data = {
                'amount': round(random.uniform(5, 50), 2),
                'method': random.choice(['cash', 'card'])
            }

            with self.client.post(
                f"/api/orders/{self.last_order_id}/add_payment/",
                json=payment_data,
                headers={'Content-Type': 'application/json'},
                catch_response=True
            ) as response:
                if response.status_code in [200, 400]:  # 400 for overpayment
                    response.success()
                else:
                    response.failure(f"Add payment failed: {response.status_code}")

    @tag('purchase')
    @task(2)
    def view_order_history(self):
        """View customer's order history."""
        customer_id = self.customer_id or random.randint(1, 100)
        with self.client.get(f"/api/orders/?customer={customer_id}", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Order history failed: {response.status_code}")

class AdminUser(EcommerceUser):
    """Administrative user performing management tasks."""

    weight = 5  # 5% of users are admins

    @tag('admin')
    @task(2)
    def generate_reports(self):
        """Generate financial reports."""
        # P&L Report
        with self.client.get(
            f"/api/revenue/pl_report/?branch={self.branch_id}&period=month",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"P&L report failed: {response.status_code}")

    @tag('admin')
    @task(1)
    def export_data(self):
        """Export data (PDF/Excel)."""
        export_type = random.choice(['pdf', 'excel'])
        with self.client.get(
            f"/api/export/pl/?format={export_type}&branch={self.branch_id}",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Export failed: {response.status_code}")

    @tag('admin')
    @task(3)
    def manage_inventory(self):
        """Update product inventory."""
        product_id = random.randint(1, 50)
        update_data = {
            'stock_quantity': random.randint(0, 200)
        }

        with self.client.patch(
            f"/api/products/{product_id}/",
            json=update_data,
            headers={'Content-Type': 'application/json'},
            catch_response=True
        ) as response:
            if response.status_code in [200, 404]:  # 404 acceptable for random IDs
                response.success()
            else:
                response.failure(f"Inventory update failed: {response.status_code}")

class HighLoadUser(EcommerceUser):
    """User simulating high load scenarios (stress testing)."""

    weight = 0  # Disabled by default, enable for stress testing
    wait_time = between(0.1, 0.5)  # Very fast interactions

    @tag('stress')
    @task
    def rapid_orders(self):
        """Create orders as fast as possible."""
        # Simplified order for speed
        order_data = {
            'customer': random.randint(1, 100),
            'branch': self.branch_id,
            'items': [{
                'variant': random.randint(1, 200),
                'quantity': 1,
                'unit_price': 10.00
            }],
            'payments': [{
                'amount': 10.00,
                'method': 'cash'
            }]
        }

        self.client.post(
            "/api/orders/",
            json=order_data,
            headers={'Content-Type': 'application/json'}
        )

# Load testing configuration
# Run with: locust -f locust_load_test.py --host=http://localhost:8000
# Web UI: http://localhost:8089
# For headless: locust -f locust_load_test.py --host=http://localhost:8000 --no-web -c 100 -r 10 --run-time 5m