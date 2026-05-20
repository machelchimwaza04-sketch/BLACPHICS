import pytest
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from branches.models import Branch

User = get_user_model()


@pytest.mark.django_db
class AuthenticationSecurityTests(APITestCase):
    """Test authentication security scenarios"""

    def setUp(self):
        """Set up test data"""
        self.branch = Branch.objects.create(
            name="Test Branch",
            city="Test City",
            address="Test Address",
            phone="+1234567890",
            email="test@branch.com"
        )

        self.admin_user = User.objects.create_user(
            username='admin',
            password='admin123!',
            role='admin'
        )

        self.manager_user = User.objects.create_user(
            username='manager',
            password='manager123!',
            role='branch_manager',
            branch=self.branch
        )

        self.cashier_user = User.objects.create_user(
            username='cashier',
            password='cashier123!',
            role='cashier',
            branch=self.branch
        )

    def test_valid_login_admin(self):
        """Test AUTH-001: Valid admin login"""
        url = reverse('login')
        data = {'username': 'admin', 'password': 'admin123!'}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['role'], 'admin')

    def test_invalid_login_attempts(self):
        """Test AUTH-002: Invalid login scenarios"""
        url = reverse('login')

        # Wrong username
        response = self.client.post(url, {
            'username': 'wrong',
            'password': 'admin123!'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Wrong password
        response = self.client.post(url, {
            'username': 'admin',
            'password': 'wrong'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Empty credentials
        response = self.client.post(url, {
            'username': '',
            'password': ''
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sql_injection_attempt(self):
        """Test AUTH-002: SQL injection prevention"""
        url = reverse('login')

        response = self.client.post(url, {
            'username': "admin'--",
            'password': 'test'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn('error', response.data)  # No detailed error exposure


@pytest.mark.django_db
class TokenHandlingTests(APITestCase):
    """Test token validation and refresh scenarios"""

    def setUp(self):
        self.branch = Branch.objects.create(
            name="Test Branch",
            city="Test City",
            address="Test Address",
            phone="+1234567890",
            email="test@branch.com"
        )

        self.user = User.objects.create_user(
            username='testuser',
            password='test123!',
            role='cashier',
            branch=self.branch
        )

    def test_token_authentication(self):
        """Test TOKEN-001: Valid token authentication"""
        # Login to get token
        login_url = reverse('login')
        login_response = self.client.post(login_url, {
            'username': 'testuser',
            'password': 'test123!'
        }, format='json')

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        access_token = login_response.data['access']

        # Use token for authenticated request
        user_url = reverse('current-user')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

        response = self.client.get(user_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')

    def test_invalid_token_rejection(self):
        """Test TOKEN-001: Invalid token handling"""
        user_url = reverse('current-user')

        # No token
        response = self.client.get(user_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Invalid token
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid_token')
        response = self.client.get(user_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh(self):
        """Test TOKEN-002: Token refresh functionality"""
        # Login
        login_url = reverse('login')
        login_response = self.client.post(login_url, {
            'username': 'testuser',
            'password': 'test123!'
        }, format='json')

        refresh_token = login_response.data['refresh']
        old_access_token = login_response.data['access']

        # Refresh token
        refresh_url = reverse('token-refresh')
        refresh_response = self.client.post(refresh_url, {
            'refresh': refresh_token
        }, format='json')

        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        new_access_token = refresh_response.data['access']
        new_refresh_token = refresh_response.data['refresh']

        # Verify new tokens are different
        self.assertNotEqual(old_access_token, new_access_token)
        self.assertNotEqual(refresh_token, new_refresh_token)

        # Verify old access token is invalidated
        user_url = reverse('current-user')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {old_access_token}')
        response = self.client.get(user_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@pytest.mark.django_db
class RoleBasedAccessTests(APITestCase):
    """Test role-based access control"""

    def setUp(self):
        self.branch1 = Branch.objects.create(
            name="Branch 1",
            city="City 1",
            address="Address 1",
            phone="+1234567890",
            email="branch1@test.com"
        )

        self.branch2 = Branch.objects.create(
            name="Branch 2",
            city="City 2",
            address="Address 2",
            phone="+1234567891",
            email="branch2@test.com"
        )

        self.admin = User.objects.create_user(
            username='admin',
            password='admin123!',
            role='admin'
        )

        self.manager1 = User.objects.create_user(
            username='manager1',
            password='manager123!',
            role='branch_manager',
            branch=self.branch1
        )

        self.cashier1 = User.objects.create_user(
            username='cashier1',
            password='cashier123!',
            role='cashier',
            branch=self.branch1
        )

    def _get_auth_token(self, username, password):
        """Helper to get authentication token"""
        login_url = reverse('login')
        response = self.client.post(login_url, {
            'username': username,
            'password': password
        }, format='json')
        return response.data['access']

    def test_admin_full_access(self):
        """Test RBAC-001: Admin has full access"""
        token = self._get_auth_token('admin', 'admin123!')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Admin can access user management
        users_url = reverse('user-list')
        response = self.client.get(users_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see all users
        self.assertGreaterEqual(len(response.data), 3)

    def test_branch_manager_limited_access(self):
        """Test RBAC-002: Branch manager has limited access"""
        token = self._get_auth_token('manager1', 'manager123!')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Branch manager can access user management
        users_url = reverse('user-list')
        response = self.client.get(users_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should only see users from their branch (including themselves)
        branch_users = [user for user in response.data
                       if user.get('branch') == self.branch1.id]
        self.assertEqual(len(branch_users), 2)  # manager1 and cashier1

    def test_cashier_restricted_access(self):
        """Test RBAC-003: Cashier has restricted access"""
        token = self._get_auth_token('cashier1', 'cashier123!')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Cashier cannot access user management
        users_url = reverse('user-list')
        response = self.client.get(users_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@pytest.mark.django_db
class BranchIsolationTests(APITestCase):
    """Test branch-level data isolation"""

    def setUp(self):
        self.branch1 = Branch.objects.create(
            name="Branch 1",
            city="City 1",
            address="Address 1",
            phone="+1234567890",
            email="branch1@test.com"
        )

        self.branch2 = Branch.objects.create(
            name="Branch 2",
            city="City 2",
            address="Address 2",
            phone="+1234567891",
            email="branch2@test.com"
        )

        self.manager1 = User.objects.create_user(
            username='manager1',
            password='manager123!',
            role='branch_manager',
            branch=self.branch1
        )

        self.manager2 = User.objects.create_user(
            username='manager2',
            password='manager123!',
            role='branch_manager',
            branch=self.branch2
        )

    def _get_auth_token(self, username, password):
        """Helper to get authentication token"""
        login_url = reverse('login')
        response = self.client.post(login_url, {
            'username': username,
            'password': password
        }, format='json')
        return response.data['access']

    def test_branch_data_isolation(self):
        """Test BRANCH-001: Branch-scoped data filtering"""
        # This test assumes Order model exists and has branch field
        # Adapt based on actual model structure

        token1 = self._get_auth_token('manager1', 'manager123!')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token1}')

        # Manager1 should only see branch1 data
        branches_url = reverse('branch-list')
        response = self.client.get(branches_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should only see their own branch
        branch_ids = [branch['id'] for branch in response.data]
        self.assertIn(self.branch1.id, branch_ids)
        self.assertNotIn(self.branch2.id, branch_ids)

    def test_cross_branch_access_prevention(self):
        """Test BRANCH-002: Cross-branch access prevention"""
        token1 = self._get_auth_token('manager1', 'manager123!')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token1}')

        # Try to access branch2 details
        branch_detail_url = reverse('branch-detail', kwargs={'pk': self.branch2.id})
        response = self.client.get(branch_detail_url)

        # Should get 404 (object not found due to filtering)
        # or 403 (forbidden) depending on implementation
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])


# Performance test example (requires pytest-benchmark)
@pytest.mark.django_db
class AuthenticationPerformanceTests(APITestCase):
    """Performance tests for authentication system"""

    def setUp(self):
        self.branch = Branch.objects.create(
            name="Test Branch",
            city="Test City",
            address="Test Address",
            phone="+1234567890",
            email="test@branch.com"
        )

        self.user = User.objects.create_user(
            username='perfuser',
            password='perf123!',
            role='cashier',
            branch=self.branch
        )

    def test_login_performance(self, benchmark):
        """Test PERF-001: Login performance"""
        url = reverse('login')
        data = {'username': 'perfuser', 'password': 'perf123!'}

        # Benchmark login request
        result = benchmark(self.client.post, url, data, format='json')

        assert result.status_code == status.HTTP_200_OK
        assert 'access' in result.data