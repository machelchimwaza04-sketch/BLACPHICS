from celery import shared_task
from datetime import date
from finance.finance_service import FinanceService
from branches.models import Branch


@shared_task
def create_daily_snapshots():
    """
    Daily Celery task to create P&L snapshots for all branches.
    Runs at 00:01 every day (see celery.py beat_schedule).
    """
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
