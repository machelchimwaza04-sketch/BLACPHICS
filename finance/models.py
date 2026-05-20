from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.core.exceptions import ValidationError
from django.utils import timezone
from branches.models import Branch


class ExpenseCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Expense Categories"


class Expense(models.Model):
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='expenses'
    )
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.SET_NULL, null=True, related_name='expenses'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    receipt = models.ImageField(upload_to='receipts/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.amount} ({self.branch.name})"

    class Meta:
        ordering = ['-date']


class Revenue(models.Model):
    SOURCE_CHOICES = [
        ('sales', 'Product Sales'),
        ('sale', 'Sale'),
        ('customization', 'Customization Fees'),
        ('refund', 'Refund received'),
        ('investment', 'Investment'),
        ('grant', 'Grant'),
        ('other', 'Other'),
    ]

    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='revenues'
    )
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='sales')
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.source} - {self.amount} ({self.branch.name})"

    class Meta:
        ordering = ['-date']


class ProfitLossReport(models.Model):
    PERIOD_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]

    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='reports'
    )
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.branch.name} - {self.period} report ({self.start_date} to {self.end_date})"

    @property
    def net_profit(self):
        return self.total_revenue - self.total_expenses

    @property
    def is_profitable(self):
        return self.net_profit > 0

    class Meta:
        ordering = ['-start_date']


class DailyPLSnapshot(models.Model):
    """
    Daily P&L snapshot for instant historical reporting.
    Populated daily at midnight via Celery task or management command.
    """
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='daily_pl_snapshots'
    )
    snapshot_date = models.DateField()

    # Sales
    sales_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_sales = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_collected = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    order_count = models.IntegerField(default=0)

    # COGS & Profit
    cogs = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gross_profit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gross_margin_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Expenses
    manual_expenses = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    supplier_payments = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Revenue
    manual_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Totals
    total_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_expenses = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_profit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_margin_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-snapshot_date']
        unique_together = [['branch', 'snapshot_date']]
        verbose_name = 'Daily P&L snapshot'
        indexes = [
            models.Index(fields=['-snapshot_date']),
            models.Index(fields=['branch', '-snapshot_date']),
        ]

    def __str__(self):
        return f'{self.branch.name} - {self.snapshot_date}'


class Account(models.Model):
    ASSET = 'asset'
    LIABILITY = 'liability'
    EQUITY = 'equity'
    REVENUE = 'revenue'
    EXPENSE = 'expense'
    COST_OF_SALES = 'cogs'

    ACCOUNT_TYPES = [
        (ASSET, 'Asset'),
        (LIABILITY, 'Liability'),
        (EQUITY, 'Equity'),
        (REVENUE, 'Revenue'),
        (EXPENSE, 'Expense'),
        (COST_OF_SALES, 'Cost of Goods Sold'),
    ]

    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='accounts', null=True, blank=True
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    parent = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True, related_name='children'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']
        verbose_name = 'General Ledger Account'
        verbose_name_plural = 'General Ledger Accounts'
        unique_together = [['branch', 'code']]
        indexes = [models.Index(fields=['branch', 'code'])]

    def __str__(self):
        return f"{self.code} - {self.name}"


class AccountingPeriod(models.Model):
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='accounting_periods'
    )
    start_date = models.DateField()
    end_date = models.DateField()
    is_closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        unique_together = [['branch', 'start_date', 'end_date']]
        verbose_name = 'Accounting Period'
        verbose_name_plural = 'Accounting Periods'

    def __str__(self):
        return f"{self.branch.name} ({self.start_date} to {self.end_date})"


class ReconciliationRun(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='reconciliation_runs'
    )
    as_of_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    summary = models.JSONField(default=dict, blank=True)
    issues = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-as_of_date', '-created_at']
        indexes = [models.Index(fields=['branch', 'as_of_date'])]

    def __str__(self):
        return f"Reconciliation for {self.branch.name} as of {self.as_of_date}"


class JournalEntry(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled'),
    ]

    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='journal_entries'
    )
    reference = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    entry_date = models.DateField(default=timezone.now)
    accounting_period = models.ForeignKey(
        'AccountingPeriod', on_delete=models.PROTECT, null=True, blank=True, related_name='journal_entries'
    )
    source_document_type = models.CharField(max_length=100, blank=True)
    source_document_id = models.CharField(max_length=100, blank=True)
    idempotency_key = models.CharField(max_length=128, blank=True, null=True, db_index=True)
    reversal_of = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True, related_name='reversal_entries'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='journal_entries'
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='posted_journal_entries'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-entry_date', '-created_at']
        verbose_name = 'Journal Entry'
        verbose_name_plural = 'Journal Entries'
        unique_together = [['branch', 'idempotency_key']]
        indexes = [models.Index(fields=['branch', 'entry_date'])]

    def __str__(self):
        return f"{self.reference or 'JE'} - {self.branch.name} - {self.entry_date}"

    @property
    def debit_total(self):
        return self.lines.filter(line_type='debit').aggregate(total=Sum('amount'))['total'] or 0

    @property
    def credit_total(self):
        return self.lines.filter(line_type='credit').aggregate(total=Sum('amount'))['total'] or 0

    @property
    def is_balanced(self):
        return self.debit_total == self.credit_total

    @property
    def is_posted(self):
        return self.status == 'posted'

    def clean(self):
        if self.status == 'posted' and not self.is_balanced:
            raise ValidationError('Journal entry must be balanced before posting.')

        if self.accounting_period:
            if not (self.accounting_period.start_date <= self.entry_date <= self.accounting_period.end_date):
                raise ValidationError('Journal entry date must be inside the assigned accounting period.')
            if self.accounting_period.is_closed:
                raise ValidationError('Cannot post into a closed accounting period.')

    def save(self, *args, **kwargs):
        if self.pk:
            existing = JournalEntry.objects.filter(pk=self.pk).first()
            if existing and existing.status == 'posted':
                immutable_fields = ['branch_id', 'reference', 'description', 'entry_date', 'accounting_period_id', 'created_by_id']
                for field in immutable_fields:
                    if getattr(existing, field) != getattr(self, field):
                        raise ValidationError('Cannot modify a posted journal entry.')
                if self.status != existing.status:
                    raise ValidationError('Cannot change status of a posted journal entry.')

        self.full_clean()
        super().save(*args, **kwargs)

    def post(self, posted_by=None):
        if not self.is_balanced:
            raise ValidationError('Cannot post an unbalanced journal entry.')
        if self.accounting_period is None:
            raise ValidationError('Journal entry must be assigned to an open accounting period before posting.')
        if self.accounting_period.is_closed:
            raise ValidationError('Cannot post into a closed accounting period.')
        self.status = 'posted'
        self.posted_at = timezone.now()
        if posted_by is not None:
            self.posted_by = posted_by
        self.save(update_fields=['status', 'posted_at', 'posted_by'])

    def cancel(self):
        if self.status == 'posted':
            raise ValidationError('Cannot cancel a posted journal entry. Use a reversal entry instead.')
        self.status = 'cancelled'
        self.save(update_fields=['status'])

    def reverse(self, created_by=None, reference=None, description=None, idempotency_key=None):
        if self.status != 'posted':
            raise ValidationError('Only posted journal entries may be reversed.')
        reversal_reference = reference or f"REV-{self.reference or self.id}"
        reversal_description = description or f"Reversal of {self.reference or self.id}"
        reversed_entry = JournalEntry.objects.create(
            branch=self.branch,
            reference=reversal_reference,
            description=reversal_description,
            entry_date=timezone.now().date(),
            accounting_period=self.accounting_period,
            source_document_type='journal_reversal',
            source_document_id=str(self.id),
            idempotency_key=idempotency_key,
            reversal_of=self,
            created_by=created_by,
            status='draft'
        )
        for line in self.lines.all():
            reversed_line_type = 'credit' if line.line_type == 'debit' else 'debit'
            JournalLine.objects.create(
                entry=reversed_entry,
                account=line.account,
                line_type=reversed_line_type,
                amount=line.amount,
                description=f"Reversal of line {line.id}: {line.description}",
                reference=line.reference,
            )
        reversed_entry.post(posted_by=created_by)
        return reversed_entry


class JournalLine(models.Model):
    LINE_TYPES = [
        ('debit', 'Debit'),
        ('credit', 'Credit'),
    ]

    entry = models.ForeignKey(
        JournalEntry, on_delete=models.CASCADE, related_name='lines'
    )
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name='journal_lines'
    )
    line_type = models.CharField(max_length=10, choices=LINE_TYPES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.TextField(blank=True)
    reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['entry', 'line_type']
        verbose_name = 'Journal Line'
        verbose_name_plural = 'Journal Lines'

    def save(self, *args, **kwargs):
        if self.amount <= 0:
            raise ValidationError('Journal line amount must be greater than zero.')
        if self.entry and self.entry.status == 'posted':
            raise ValidationError('Cannot modify journal lines for a posted entry.')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.entry.reference or self.entry.id} - {self.line_type.title()} {self.amount} on {self.account.code}"
