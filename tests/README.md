# Blacphics Authentication System - Test Suite

This directory contains comprehensive API tests for the authentication and authorization system.

## Test Coverage

### 1. Authentication Security Tests (`test_authentication.py`)
- ✅ Valid login scenarios for all user roles
- ✅ Invalid login attempts (wrong credentials, SQL injection, XSS)
- ✅ Disabled account handling
- ✅ Token validation and expiration
- ✅ Token refresh mechanism
- ✅ Logout and token blacklisting

### 2. Role-Based Access Control Tests (`test_authentication.py`)
- ✅ Admin full system access
- ✅ Branch manager permissions (own branch + user management)
- ✅ Cashier restricted access (read-only + order creation)
- ✅ Permission escalation prevention

### 3. Branch Isolation Tests (`test_branch_isolation.py`)
- ✅ Automatic branch-based data filtering
- ✅ Cross-branch access prevention
- ✅ Branch user management restrictions
- ✅ Integration with business logic (orders, customers, products)

## Test Fixtures

The `conftest.py` file provides reusable fixtures:
- `test_branch`: Creates a test branch
- `admin_user`, `branch_manager`, `cashier`: Creates test users
- `api_client`: Django REST framework test client
- `authenticated_client`: Pre-authenticated client as admin
- `manager_client`, `cashier_client`: Pre-authenticated clients for other roles

## Running Tests

### Prerequisites
1. Install test dependencies:
```bash
pip install pytest pytest-django pytest-cov pytest-benchmark
```

2. Set up test database:
```bash
python manage.py migrate
```

3. Create test users:
```bash
python manage.py create_initial_users
```

### Run All Tests
```bash
pytest
```

### Run Specific Test Categories
```bash
# Authentication tests
pytest tests/test_authentication.py -v

# Branch isolation tests
pytest tests/test_branch_isolation.py -v

# Run with coverage
pytest --cov=branches --cov-report=html

# Run performance tests
pytest -k "performance" --benchmark-only
```

### Run Single Test
```bash
pytest tests/test_authentication.py::AuthenticationSecurityTests::test_valid_login_admin -v
```

## Test Data Setup

Tests automatically create:
- 2 test branches (Branch 1, Branch 2)
- Admin, branch manager, and cashier users
- Sample customers, products, and orders per branch

## Continuous Integration

Add to your CI pipeline:
```yaml
- name: Run Authentication Tests
  run: |
    pip install -r requirements.txt
    pip install pytest pytest-django pytest-cov
    python manage.py migrate
    python manage.py create_initial_users
    pytest --cov=branches --cov-fail-under=80
```

## Security Test Checklist

Before deployment, ensure all tests pass:

### Authentication Security
- [ ] Valid login for all roles
- [ ] Invalid credential rejection
- [ ] SQL injection prevention
- [ ] XSS prevention
- [ ] Disabled account handling

### Token Security
- [ ] Access token validation
- [ ] Refresh token rotation
- [ ] Token blacklisting on logout
- [ ] Expired token handling

### Authorization
- [ ] Admin full access
- [ ] Branch manager scoped access
- [ ] Cashier limited access
- [ ] No privilege escalation

### Branch Isolation
- [ ] Data filtering by branch
- [ ] Cross-branch access blocked
- [ ] User management scoped to branch
- [ ] Business logic respects branches

## Performance Benchmarks

Run performance tests to ensure:
- Login response time < 500ms
- Token validation < 100ms
- API calls with auth < 200ms
- Concurrent requests handled properly

## Adding New Tests

1. Create test methods following the naming pattern: `test_descriptive_name`
2. Use fixtures from `conftest.py` for common setup
3. Include docstrings explaining what is being tested
4. Add assertions for both positive and negative cases
5. Test edge cases and error conditions

Example:
```python
def test_new_feature(self, authenticated_client):
    """Test that new feature works correctly"""
    response = authenticated_client.get('/api/new-endpoint/')
    self.assertEqual(response.status_code, 200)
    self.assertIn('expected_data', response.data)
```

## Troubleshooting

### Common Issues
1. **Migration errors**: Run `python manage.py migrate` first
2. **Missing fixtures**: Ensure `conftest.py` is in the tests directory
3. **Import errors**: Check that all required apps are in INSTALLED_APPS
4. **Permission errors**: Verify user roles and branch assignments

### Debug Mode
Run tests with verbose output:
```bash
pytest -v -s --tb=long
```

### Coverage Reports
Generate HTML coverage report:
```bash
pytest --cov=branches --cov-report=html
# Open htmlcov/index.html in browser
```