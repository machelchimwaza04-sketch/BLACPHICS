"""
Distributed locking utilities for production-grade concurrency control.
Uses Redis for cross-process locking to prevent race conditions.
"""

import redis
import time
from contextlib import contextmanager
from django.conf import settings
from django.core.cache import cache


class DistributedLock:
    """
    Redis-based distributed lock for preventing race conditions across processes.
    """

    def __init__(self, lock_key, timeout=30, retry_delay=0.1, max_retries=50):
        self.lock_key = f"lock:{lock_key}"
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.max_retries = max_retries
        self.redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)

    def acquire(self):
        """Acquire the lock with retry logic."""
        for attempt in range(self.max_retries):
            if self.redis_client.set(self.lock_key, 'locked', ex=self.timeout, nx=True):
                return True
            time.sleep(self.retry_delay)
        return False

    def release(self):
        """Release the lock."""
        self.redis_client.delete(self.lock_key)

    @contextmanager
    def __enter__(self):
        if not self.acquire():
            raise Exception(f"Failed to acquire lock: {self.lock_key}")
        try:
            yield
        finally:
            self.release()


def get_inventory_lock(branch_id, product_id, variant_id=None):
    """Get a distributed lock for inventory operations."""
    key_parts = ['inventory', str(branch_id), str(product_id)]
    if variant_id:
        key_parts.append(str(variant_id))
    return DistributedLock(':'.join(key_parts), timeout=60)


def get_order_lock(order_id):
    """Get a distributed lock for order operations."""
    return DistributedLock(f"order:{order_id}", timeout=300)


def get_purchase_lock(purchase_id):
    """Get a distributed lock for purchase operations."""
    return DistributedLock(f"purchase:{purchase_id}", timeout=300)


def get_journal_lock(branch_id, reference):
    """Get a distributed lock for journal operations."""
    return DistributedLock(f"journal:{branch_id}:{reference}", timeout=30)