from django.core.management.base import BaseCommand
from datetime import date, timedelta
from finance.finance_service import FinanceService
from branches.models import Branch


class Command(BaseCommand):
    help = 'Create or update daily P&L snapshots for all branches'

    def add_arguments(self, parser):
        parser.add_argument(
            '--branch-id',
            type=int,
            help='Create snapshot for a specific branch ID'
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Create snapshot for a specific date (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--backfill',
            type=int,
            help='Backfill snapshots for N days'
        )

    def handle(self, *args, **options):
        branch_id = options.get('branch_id')
        snapshot_date = options.get('date')
        backfill_days = options.get('backfill')

        if snapshot_date:
            try:
                snapshot_date = datetime.strptime(snapshot_date, '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid date format. Use YYYY-MM-DD'))
                return

        if backfill_days:
            # Backfill previous N days
            for i in range(backfill_days, -1, -1):
                d = date.today() - timedelta(days=i)
                self._create_snapshot_for_date(d, branch_id)
        else:
            # Create for specific date or today
            target_date = snapshot_date or date.today()
            self._create_snapshot_for_date(target_date, branch_id)

    def _create_snapshot_for_date(self, snapshot_date, branch_id=None):
        if branch_id:
            branches = Branch.objects.filter(id=branch_id, is_active=True)
        else:
            branches = Branch.objects.filter(is_active=True)

        for branch in branches:
            try:
                snapshot = FinanceService.create_daily_snapshot(
                    branch_id=branch.id,
                    snapshot_date=snapshot_date
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Created snapshot for {branch.name} on {snapshot.snapshot_date}'
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'✗ Failed for {branch.name}: {str(e)}'
                    )
                )
