from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from branches.models import Branch
from .services import (
    get_or_create_standard_chart,
    create_journal_entry,
    close_accounting_period,
    compile_accounts_receivable_aging,
    compile_accounts_payable_aging,
    compile_cash_flow,
)


class FinanceServiceTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(
            name='Main Branch',
            city='Metro City',
            address='123 Finance St',
            phone='555-0100',
            email='main.branch@example.com',
        )
        self.user = get_user_model().objects.create_user(
            username='finance_admin',
            password='password',
            role='admin'
        )
        get_or_create_standard_chart(self.branch)

        # Open accounting period for journal posting
        from .models import AccountingPeriod
        AccountingPeriod.objects.create(
            branch=self.branch,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=30),
            is_closed=False,
        )

    def test_accounts_receivable_aging_uses_general_ledger(self):
        ar_account = self.branch.accounts.get(code='1100')
        sales_account = self.branch.accounts.get(code='4000')

        create_journal_entry(
            branch=self.branch,
            created_by=self.user,
            reference='INV-100',
            description='Sale invoice',
            entry_date=date.today() - timedelta(days=45),
            source_document_type='Order',
            source_document_id='100',
            lines=[
                {'account': ar_account, 'line_type': 'debit', 'amount': Decimal('250.00')},
                {'account': sales_account, 'line_type': 'credit', 'amount': Decimal('250.00')},
            ],
        )
        create_journal_entry(
            branch=self.branch,
            created_by=self.user,
            reference='PMT-100',
            description='Customer payment',
            entry_date=date.today() - timedelta(days=30),
            source_document_type='Order',
            source_document_id='100',
            lines=[
                {'account': self.branch.accounts.get(code='1000'), 'line_type': 'debit', 'amount': Decimal('150.00')},
                {'account': ar_account, 'line_type': 'credit', 'amount': Decimal('150.00')},
            ],
        )

        result = compile_accounts_receivable_aging(branch=self.branch, as_of_date=date.today())

        self.assertEqual(result['ledger_balance'], Decimal('100.00'))
        self.assertEqual(result['aging']['30_days'], Decimal('100.00'))
        self.assertEqual(result['variance'], Decimal('0.00'))

    def test_accounts_payable_aging_uses_general_ledger(self):
        ap_account = self.branch.accounts.get(code='2000')
        inventory_account = self.branch.accounts.get(code='1200')

        create_journal_entry(
            branch=self.branch,
            created_by=self.user,
            reference='PUR-100',
            description='Purchase invoice',
            entry_date=date.today() - timedelta(days=70),
            source_document_type='Purchase',
            source_document_id='100',
            lines=[
                {'account': inventory_account, 'line_type': 'debit', 'amount': Decimal('500.00')},
                {'account': ap_account, 'line_type': 'credit', 'amount': Decimal('500.00')},
            ],
        )
        create_journal_entry(
            branch=self.branch,
            created_by=self.user,
            reference='SUP-100',
            description='Supplier payment',
            entry_date=date.today() - timedelta(days=40),
            source_document_type='Purchase',
            source_document_id='100',
            lines=[
                {'account': ap_account, 'line_type': 'debit', 'amount': Decimal('200.00')},
                {'account': self.branch.accounts.get(code='1000'), 'line_type': 'credit', 'amount': Decimal('200.00')},
            ],
        )

        result = compile_accounts_payable_aging(branch=self.branch, as_of_date=date.today())

        self.assertEqual(result['ledger_balance'], Decimal('300.00'))
        self.assertEqual(result['aging']['60_days'], Decimal('300.00'))
        self.assertEqual(result['variance'], Decimal('0.00'))

    def test_cash_flow_links_to_general_ledger(self):
        cash_account = self.branch.accounts.get(code='1000')
        ar_account = self.branch.accounts.get(code='1100')

        create_journal_entry(
            branch=self.branch,
            created_by=self.user,
            reference='CF-100',
            description='Cash receipt',
            entry_date=date.today() - timedelta(days=5),
            source_document_type='Order',
            source_document_id='200',
            lines=[
                {'account': cash_account, 'line_type': 'debit', 'amount': Decimal('120.00')},
                {'account': ar_account, 'line_type': 'credit', 'amount': Decimal('120.00')},
            ],
        )

        cash_flow = compile_cash_flow(branch=self.branch, start_date=date.today() - timedelta(days=30), end_date=date.today())

        self.assertEqual(cash_flow['cash_inflow'], Decimal('120.00'))
        self.assertEqual(cash_flow['cash_outflow'], Decimal('0.00'))
        self.assertEqual(cash_flow['net_cash_flow'], Decimal('120.00'))
        self.assertEqual(cash_flow['operating_cash_flow'], Decimal('120.00'))

    def test_duplicate_source_document_journal_entry_is_idempotent(self):
        ar_account = self.branch.accounts.get(code='1100')
        sales_account = self.branch.accounts.get(code='4000')

        entry_one = create_journal_entry(
            branch=self.branch,
            created_by=self.user,
            reference='INV-200',
            description='Sale invoice',
            entry_date=date.today() - timedelta(days=5),
            source_document_type='Order',
            source_document_id='200',
            lines=[
                {'account': ar_account, 'line_type': 'debit', 'amount': Decimal('100.00')},
                {'account': sales_account, 'line_type': 'credit', 'amount': Decimal('100.00')},
            ],
        )

        entry_two = create_journal_entry(
            branch=self.branch,
            created_by=self.user,
            reference='INV-200-RETRY',
            description='Duplicate sale invoice',
            entry_date=date.today() - timedelta(days=5),
            source_document_type='Order',
            source_document_id='200',
            lines=[
                {'account': ar_account, 'line_type': 'debit', 'amount': Decimal('100.00')},
                {'account': sales_account, 'line_type': 'credit', 'amount': Decimal('100.00')},
            ],
        )

        self.assertEqual(entry_one.id, entry_two.id)
        self.assertEqual(entry_one.reference, 'INV-200')

    def test_close_accounting_period_rolls_up_profit_and_closes(self):
        revenue_account = self.branch.accounts.get(code='4000')
        expense_account = self.branch.accounts.get(code='6000')
        cash_account = self.branch.accounts.get(code='1000')

        create_journal_entry(
            branch=self.branch,
            created_by=self.user,
            reference='REV-100',
            description='Revenue entry',
            entry_date=date.today() - timedelta(days=10),
            lines=[
                {'account': cash_account, 'line_type': 'debit', 'amount': Decimal('300.00')},
                {'account': revenue_account, 'line_type': 'credit', 'amount': Decimal('300.00')},
            ],
        )

        create_journal_entry(
            branch=self.branch,
            created_by=self.user,
            reference='EXP-100',
            description='Expense entry',
            entry_date=date.today() - timedelta(days=5),
            lines=[
                {'account': expense_account, 'line_type': 'debit', 'amount': Decimal('120.00')},
                {'account': cash_account, 'line_type': 'credit', 'amount': Decimal('120.00')},
            ],
        )

        from .models import AccountingPeriod
        period = AccountingPeriod.objects.get(branch=self.branch, is_closed=False)

        closed_period = close_accounting_period(period, created_by=self.user)

        self.assertTrue(closed_period.is_closed)
        self.assertTrue(closed_period.journal_entries.filter(source_document_type='accounting_period_close').exists())
        closing_entry = closed_period.journal_entries.get(source_document_type='accounting_period_close')
        self.assertEqual(closing_entry.status, 'posted')
        self.assertEqual(closing_entry.debit_total, closing_entry.credit_total)
