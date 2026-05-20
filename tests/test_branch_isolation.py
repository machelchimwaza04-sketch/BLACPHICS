import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from branches.models import Branch
from customers.models import Customer
from orders.models import Order
from products.models import Product, ProductVariant


@pytest.mark.django_db
class BranchIsolationIntegrationTests(TestCase):
    """Integration tests for branch isolation in business logic"""

    def setUp(self):
        # Create branches
        self.branch1 = Branch.objects.create(
            name="Branch 1", city="City 1", address="Addr 1",
            phone="+1234567890", email="b1@test.com"
        )
        self.branch2 = Branch.objects.create(
            name="Branch 2", city="City 2", address="Addr 2",
            phone="+1234567891", email="b2@test.com"
        )

        # Create users
        from django.contrib.auth import get_user_model
        User = get_user_model()

        self.admin = User.objects.create_user(
            username='admin', password='admin123!', role='admin'
        )
        self.manager1 = User.objects.create_user(
            username='manager1', password='manager123!',
            role='branch_manager', branch=self.branch1
        )
        self.cashier1 = User.objects.create_user(
            username='cashier1', password='cashier123!',
            role='cashier', branch=self.branch1
        )

        # Create customers
        self.customer1 = Customer.objects.create(
            first_name="Customer", last_name="One",
            email="c1@test.com", phone="+1234567001",
            branch=self.branch1
        )
        self.customer2 = Customer.objects.create(
            first_name="Customer", last_name="Two",
            email="c2@test.com", phone="+1234567002",
            branch=self.branch2
        )

        # Create products and variants
        self.product1 = Product.objects.create(
            name="Product 1",
            base_price=10.00,
            item_type='plain',
            branch=self.branch1
        )
        self.variant1 = ProductVariant.objects.create(
            product=self.product1,
            size="M", color="Blue",
            stock_quantity=100,
            committed_quantity=0
        )

        self.product2 = Product.objects.create(
            name="Product 2",
            base_price=20.00,
            item_type='plain',
            branch=self.branch2
        )
        self.variant2 = ProductVariant.objects.create(
            product=self.product2,
            size="L", color="Red",
            stock_quantity=50,
            committed_quantity=0
        )

    def _get_auth_token(self, username, password):
        """Helper to get authentication token"""
        from rest_framework.test import APIClient
        client = APIClient()
        login_url = reverse('login')
        response = client.post(login_url, {
            'username': username,
            'password': password
        }, format='json')
        return response.data['access']

    def test_branch_manager_sees_only_own_branch_orders(self):
        """Test that branch managers only see orders from their branch"""
        # Create orders in both branches
        order1 = Order.objects.create(
            branch=self.branch1,
            customer=self.customer1,
            order_number="ORD-001",
            total_amount=10.00,
            amount_paid=10.00,
            payment_status='paid',
            created_by=self.cashier1
        )

        order2 = Order.objects.create(
            branch=self.branch2,
            customer=self.customer2,
            order_number="ORD-002",
            total_amount=20.00,
            amount_paid=20.00,
            payment_status='paid'
        )

        # Login as branch manager 1
        token = self._get_auth_token('manager1', 'manager123!')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Get orders
        orders_url = reverse('order-list')
        response = client.get(orders_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response_data = response.json()
        # Should only see order from branch 1
        order_ids = [order['id'] for order in response_data['results']]
        self.assertIn(order1.id, order_ids)
        self.assertNotIn(order2.id, order_ids)

    def test_admin_sees_all_branches_orders(self):
        """Test that admin sees orders from all branches"""
        # Create orders in both branches
        order1 = Order.objects.create(
            branch=self.branch1,
            customer=self.customer1,
            order_number="ORD-001",
            total_amount=10.00,
            amount_paid=10.00,
            payment_status='paid'
        )

        order2 = Order.objects.create(
            branch=self.branch2,
            customer=self.customer2,
            order_number="ORD-002",
            total_amount=20.00,
            amount_paid=20.00,
            payment_status='paid'
        )

        # Login as admin
        token = self._get_auth_token('admin', 'admin123!')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Get orders
        orders_url = reverse('order-list')
        response = client.get(orders_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response_data = response.json()
        # Should see orders from both branches
        order_ids = [order['id'] for order in response_data['results']]
        self.assertIn(order1.id, order_ids)
        self.assertIn(order2.id, order_ids)

    def test_cross_branch_access_prevention(self):
        """Test that users cannot access other branches' data directly"""
        # Create order in branch 2
        order2 = Order.objects.create(
            branch=self.branch2,
            customer=self.customer2,
            order_number="ORD-002",
            total_amount=20.00,
            amount_paid=20.00,
            payment_status='paid'
        )

        # Login as branch manager 1
        token = self._get_auth_token('manager1', 'manager123!')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Try to access order from branch 2 directly
        order_detail_url = reverse('order-detail', kwargs={'pk': order2.id})
        response = client.get(order_detail_url)

        # Should get 404 (filtered out) or 403 (forbidden)
        self.assertIn(response.status_code,
                     [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_cashier_can_create_orders(self):
        """Test that cashiers can create orders in their branch"""
        token = self._get_auth_token('cashier1', 'cashier123!')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        orders_url = reverse('order-list')
        order_data = {
            'customer': self.customer1.id,
            'order_number': 'ORD-003',
            'total_amount': '15.00',
            'amount_paid': '15.00',
            'payment_status': 'paid',
            'status': 'completed'
        }

        response = client.post(orders_url, order_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('branch'), self.branch1.id)

    def test_cashier_cannot_create_orders_in_other_branch(self):
        """Test that cashiers cannot create orders with an explicit branch override"""
        token = self._get_auth_token('cashier1', 'cashier123!')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        orders_url = reverse('order-list')
        order_data = {
            'branch': self.branch2.id,  # Explicit branch override should be rejected
            'customer': self.customer2.id,
            'order_number': 'ORD-004',
            'total_amount': '25.00',
            'amount_paid': '25.00',
            'payment_status': 'paid',
            'status': 'completed'
        }

        response = client.post(orders_url, order_data, format='json')

        # Should fail due to branch validation
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cashier_branch_is_always_derived_from_user_on_create(self):
        """Branch is assigned from the authenticated user, even when not provided."""
        token = self._get_auth_token('cashier1', 'cashier123!')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        orders_url = reverse('order-list')
        order_data = {
            'customer': self.customer1.id,
            'order_number': 'ORD-005',
            'total_amount': '15.00',
            'amount_paid': '15.00',
            'payment_status': 'paid',
            'status': 'completed'
        }

        response = client.post(orders_url, order_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('branch'), self.branch1.id)

    def test_cashier_cannot_override_branch_on_order_update(self):
        """Updating order data must not allow changing the branch."""
        order = Order.objects.create(
            branch=self.branch1,
            customer=self.customer1,
            order_number='ORD-006',
            total_amount=30.00,
            amount_paid=30.00,
            payment_status='paid'
        )

        token = self._get_auth_token('cashier1', 'cashier123!')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        order_detail_url = reverse('order-detail', kwargs={'pk': order.id})
        response = client.patch(order_detail_url, {'branch': self.branch2.id}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        order.refresh_from_db()
        self.assertEqual(order.branch_id, self.branch1.id)