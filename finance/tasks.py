from celery import shared_task
from datetime import date
from finance.finance_service import FinanceService
from finance.services import run_nightly_reconciliation
from finance.reconciliation import ReconciliationService
from branches.models import Branch
from django.core.cache import cache
from django.utils import timezone


@shared_task(bind=True)
def create_daily_snapshots(self):
    """
    Daily Celery task to create P&L snapshots for all branches.
    Runs at 00:01 every day (see celery.py beat_schedule).
    """
    # Deduplication check
    task_key = f"daily_snapshots_{date.today()}"
    if cache.get(task_key):
        return f"Daily snapshots already completed for {date.today()}"
    
    cache.set(task_key, True, 86400)  # 24 hours
    
    branches = Branch.objects.filter(is_active=True)
    
    for branch in branches:
        try:
            snapshot = FinanceService.create_daily_snapshot(
                branch_id=branch.id,
                snapshot_date=date.today()
            )
            print(f"✓ Created snapshot for {branch.name} on {snapshot.snapshot_date}")
        except Exception as e:
            print(f"✗ Failed to create snapshot for {branch.name}: {str(e)}")
    
    return f"Daily snapshots created for {branches.count()} branches"


@shared_task(bind=True)
def run_nightly_reconciliation_task(self):
    """
    Nightly reconciliation task to validate financial integrity.
    Runs at 23:59 every day (see celery.py beat_schedule).
    """
    # Deduplication check
    task_key = f"nightly_reconciliation_{date.today()}"
    if cache.get(task_key):
        return f"Nightly reconciliation already completed for {date.today()}"
    
    cache.set(task_key, True, 86400)  # 24 hours
    
    branches = Branch.objects.filter(is_active=True)
    
    for branch in branches:
        try:
            results = run_nightly_reconciliation(branch=branch, as_of_date=date.today())
            health = results['summary']['overall_health']
            critical_issues = results['summary']['critical_issues']
            warning_issues = results['summary']['warning_issues']
            
            if health == 'CRITICAL':
                print(f"⚠️  CRITICAL: {branch.name} has {critical_issues} critical issues")
            elif health == 'WARNING':
                print(f"⚠️  WARNING: {branch.name} has {warning_issues} warning issues")
            else:
                print(f"✓ {branch.name} reconciliation passed")
        except Exception as e:
            print(f"✗ Failed to run reconciliation for {branch.name}: {str(e)}")
    
    return f"Nightly reconciliation completed for {branches.count()} branches"
