from django.db import models
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
    Optional daily rollup for faster reporting and audit (populate via job or management command).
    """
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name='daily_pl_snapshots'
    )
    date = models.DateField()
    total_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_expenses = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cogs = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_profit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        unique_together = [['branch', 'date']]
        verbose_name = 'Daily P&L snapshot'

    def __str__(self):
        return f'{self.branch_id} {self.date}'