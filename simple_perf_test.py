#!/usr/bin/env python
"""
Simple Performance Test for BLACPHICS
"""

import os
import sys
import time
import django

# Django setup
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Blacphics.settings')
django.setup()

from django.test import Client

def test_basic_api():
    """Test basic API endpoints."""
    from django.conf import settings
    # Allow testserver for testing
    if 'testserver' not in settings.ALLOWED_HOSTS:
        settings.ALLOWED_HOSTS.append('testserver')

    client = Client()

    print("Testing API endpoints...")

    # Test products endpoint
    start = time.time()
    response = client.get('/api/products/?branch=1')
    duration = time.time() - start
    print(f"Products API: {duration:.3f}s - Status: {response.status_code}")

    # Test orders endpoint
    start = time.time()
    response = client.get('/api/orders/?branch=1')
    duration = time.time() - start
    print(f"Orders API: {duration:.3f}s - Status: {response.status_code}")

    print("Basic API test completed!")

if __name__ == '__main__':
    test_basic_api()