import pytest
from django.contrib.auth import get_user_model
from branches.models import Branch

User = get_user_model()


@pytest.fixture
def test_branch():
    """Create a test branch"""
    return Branch.objects.create(
        name="Test Branch",
        city="Test City",
        address="Test Address 123",
        phone="+1234567890",
        email="test@branch.com"
    )


@pytest.fixture
def admin_user():
    """Create an admin user"""
    return User.objects.create_user(
        username='admin',
        password='admin123!',
        role='admin',
        first_name='System',
        last_name='Administrator'
    )


@pytest.fixture
def branch_manager(test_branch):
    """Create a branch manager"""
    return User.objects.create_user(
        username='manager',
        password='manager123!',
        role='branch_manager',
        branch=test_branch,
        first_name='Branch',
        last_name='Manager'
    )


@pytest.fixture
def cashier(test_branch):
    """Create a cashier"""
    return User.objects.create_user(
        username='cashier',
        password='cashier123!',
        role='cashier',
        branch=test_branch,
        first_name='Test',
        last_name='Cashier'
    )


@pytest.fixture
def api_client():
    """Get Django REST framework test client"""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, admin_user):
    """Get authenticated API client as admin"""
    from django.urls import reverse

    # Login to get token
    login_url = reverse('login')
    response = api_client.post(login_url, {
        'username': 'admin',
        'password': 'admin123!'
    }, format='json')

    token = response.data['access']
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    return api_client


@pytest.fixture
def manager_client(api_client, branch_manager):
    """Get authenticated API client as branch manager"""
    from django.urls import reverse

    login_url = reverse('login')
    response = api_client.post(login_url, {
        'username': 'manager',
        'password': 'manager123!'
    }, format='json')

    token = response.data['access']
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    return api_client


@pytest.fixture
def cashier_client(api_client, cashier):
    """Get authenticated API client as cashier"""
    from django.urls import reverse

    login_url = reverse('login')
    response = api_client.post(login_url, {
        'username': 'cashier',
        'password': 'cashier123!'
    }, format='json')

    token = response.data['access']
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    return api_client