from datetime import date, timedelta
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Sum, F
from django.core.exceptions import ValidationError
from .models import Account, JournalEntry, JournalLine, AccountingPeriod, Expense, Revenue
from common.locking import get_journal_lock


def get_or_create_account(code, name, account_type, branch=None, description=''):
    queryset = Account.objects.filter(code=code, branch=branch)
    account = queryset.first()
    if account is None:
        account = Account.objects.create(
            code=code,
            name=name,
            account_type=account_type,
            branch=branch,
            description=description,
        )
    elif not account.is_active:
        account.is_active = True
        account.save(update_fields=['is_active'])
    return account


def get_account(code, branch=None):
    return Account.objects.filter(code=code, branch=branch).first()


def get_accounting_period(branch, entry_date):
    period = AccountingPeriod.objects.filter(
        branch=branch,
        start_date__lte=entry_date,
        end_date__gte=entry_date,
        is_closed=False
    ).first()
    if not period:
        raise ValidationError('No open accounting period found for entry date.')
    return period


def create_accounting_period(branch, start_date, end_date):
    if start_date > end_date:
        raise ValidationError('Accounting period start date must be before end date.')
    if AccountingPeriod.objects.filter(branch=branch, start_date__lte=end_date, end_date__gte=start_date).exists():
        raise ValidationError('An overlapping accounting period already exists for this branch.')
    return AccountingPeriod.objects.create(
        branch=branch,
        start_date=start_date,
        end_date=end_date,
        is_closed=False,
    )


def close_accounting_period(period, created_by=None):
    if period.is_closed:
        return period
    if JournalEntry.objects.filter(accounting_period=period, status='draft').exists():
        raise ValidationError('Cannot close an accounting period while draft journal entries remain.')
    if JournalEntry.objects.filter(accounting_period=period, status='posted').count() == 0:
        raise ValidationError('Cannot close an empty accounting period.')

    closing_date = period.end_date
    close_reference = f"CLOSE-{period.branch.code}-{closing_date.strftime('%Y%m%d')}"

    revenue_accounts = Account.objects.filter(branch=period.branch, account_type='revenue')
    expense_accounts = Account.objects.filter(branch=period.branch, account_type__in=['expense', 'cogs'])
    retained_earnings = get_standard_account(period.branch, '3010')
    current_year_earnings = get_standard_account(period.branch, '3100')

    closing_lines = []
    revenue_total = Decimal('0.00')
    expense_total = Decimal('0.00')

    for account in revenue_accounts:
        balance = get_account_balance(period.branch, account.code, start_date=period.start_date, end_date=period.end_date)
        if balance == 0:
            continue
        revenue_total += balance
        closing_lines.append({'account': account, 'line_type': 'debit', 'amount': abs(balance), 'description': 'Close revenue to retained earnings'})

    for account in expense_accounts:
        balance = get_account_balance(period.branch, account.code, start_date=period.start_date, end_date=period.end_date)
        if balance == 0:
            continue
        expense_total += balance
        closing_lines.append({'account': account, 'line_type': 'credit', 'amount': abs(balance), 'description': 'Close expense to retained earnings'})

    if revenue_total or expense_total:
        net_income = revenue_total - expense_total
        if net_income >= 0:
            closing_lines.append({'account': current_year_earnings, 'line_type': 'credit', 'amount': net_income, 'description': 'Record current year net income'})
            closing_lines.append({'account': retained_earnings, 'line_type': 'debit', 'amount': net_income, 'description': 'Transfer net income to retained earnings'})
        else:
            closing_lines.append({'account': current_year_earnings, 'line_type': 'debit', 'amount': abs(net_income), 'description': 'Record current year net loss'})
            closing_lines.append({'account': retained_earnings, 'line_type': 'credit', 'amount': abs(net_income), 'description': 'Transfer net loss to retained earnings'})

        create_journal_entry(
            branch=period.branch,
            created_by=created_by,
            reference=close_reference,
            description=f'Close accounting period {period.start_date} to {period.end_date}',
            entry_date=closing_date,
            lines=closing_lines,
            post=True,
            source_document_type='accounting_period_close',
            source_document_id=str(period.id),
            idempotency_key=close_reference,
        )

    period.is_closed = True
    period.save(update_fields=['is_closed'])
    return period


def reopen_accounting_period(period):
    if not period.is_closed:
        return period
    if JournalEntry.objects.filter(accounting_period__branch=period.branch, accounting_period__start_date__gt=period.start_date, accounting_period__is_closed=True).exists():
        raise ValidationError('Cannot reopen a period while a later period has been closed.')
    period.is_closed = False
    period.save(update_fields=['is_closed'])
    return period


def get_or_create_standard_chart(branch):
    standard_accounts = {
        '1000': ('Cash/Bank', 'asset'),
        '1100': ('Accounts Receivable', 'asset'),
        '1200': ('Inventory Asset', 'asset'),
        '1300': ('Prepayments', 'asset'),
        '1400': ('Tax Receivable', 'asset'),
        '1500': ('Customer Deposits', 'liability'),
        '1510': ('Customer Overpayments', 'liability'),
        '2000': ('Accounts Payable', 'liability'),
        '2100': ('Accrued Expenses', 'liability'),
        '2200': ('Tax Payable', 'liability'),
        '3000': ('Equity', 'equity'),
        '3010': ('Retained Earnings', 'equity'),
        '3100': ('Current Year Earnings', 'equity'),
        '4000': ('Sales Revenue', 'revenue'),
        '4010': ('Sales Discounts', 'revenue'),
        '4100': ('Other Revenue', 'revenue'),
        '5000': ('Cost of Goods Sold', 'cogs'),
        '5100': ('Purchase Discounts', 'cogs'),
        '5200': ('Inventory Adjustments', 'expense'),
        '6000': ('Operating Expenses', 'expense'),
        '6100': ('Bad Debt Expense', 'expense'),
        '6200': ('Inventory Shrinkage', 'expense'),
    }
    for code, (name, account_type) in standard_accounts.items():
        get_or_create_account(code=code, name=name, account_type=account_type, branch=branch)


def create_journal_entry(branch, created_by, reference, description, entry_date, lines, post=True,
                         source_document_type='', source_document_id='', idempotency_key=None,
                         reversal_of=None):
    with transaction.atomic():
        accounting_period = get_accounting_period(branch, entry_date)

        # Acquire distributed lock for journal operations
        with get_journal_lock(branch.id, reference):
            if idempotency_key:
                existing = JournalEntry.objects.filter(branch=branch, idempotency_key=idempotency_key).first()
                if existing:
                    return existing

            if source_document_type and source_document_id:
                existing = JournalEntry.objects.filter(
                    branch=branch,
                    source_document_type=source_document_type,
                    source_document_id=source_document_id,
                ).first()
                if existing:
                    return existing

            entry = JournalEntry.objects.create(
                branch=branch,
                reference=reference or '',
                description=description,
                entry_date=entry_date,
                accounting_period=accounting_period,
                created_by=created_by,
                source_document_type=source_document_type,
                source_document_id=source_document_id,
                idempotency_key=idempotency_key,
                reversal_of=reversal_of,
                status='draft',
            )

            for line in lines:
                JournalLine.objects.create(
                    entry=entry,
                    account=line['account'],
                    line_type=line['line_type'],
                    amount=Decimal(line['amount']),
                    description=line.get('description', ''),
                    reference=line.get('reference', ''),
                )
            entry.refresh_from_db()
            if not entry.is_balanced:
                raise ValidationError('Journal entry is not balanced.')
        if post:
            entry.post(posted_by=created_by)
        return entry


def post_journal_entry(entry, posted_by=None):
    with transaction.atomic():
        entry.post(posted_by=posted_by)
        return entry


def get_standard_account(branch, code):
    standard_accounts = {
        '1000': ('Cash/Bank', 'asset'),
        '1100': ('Accounts Receivable', 'asset'),
        '1200': ('Inventory Asset', 'asset'),
        '1300': ('Prepayments', 'asset'),
        '1400': ('Tax Receivable', 'asset'),
        '1500': ('Customer Deposits', 'liability'),
        '1510': ('Customer Overpayments', 'liability'),
        '2000': ('Accounts Payable', 'liability'),
        '2100': ('Accrued Expenses', 'liability'),
        '2200': ('Tax Payable', 'liability'),
        '3000': ('Equity', 'equity'),
        '3010': ('Retained Earnings', 'equity'),
        '3100': ('Current Year Earnings', 'equity'),
        '4000': ('Sales Revenue', 'revenue'),
        '4010': ('Sales Discounts', 'revenue'),
        '4100': ('Other Revenue', 'revenue'),
        '5000': ('Cost of Goods Sold', 'cogs'),
        '5100': ('Purchase Discounts', 'cogs'),
        '5200': ('Inventory Adjustments', 'expense'),
        '6000': ('Operating Expenses', 'expense'),
        '6100': ('Bad Debt Expense', 'expense'),
        '6200': ('Inventory Shrinkage', 'expense'),
    }
    if code not in standard_accounts:
        raise ValidationError(f'Unknown standard account code: {code}')
    name, account_type = standard_accounts[code]
    return get_or_create_account(code=code, name=name, account_type=account_type, branch=branch)


def record_customer_payment(branch, created_by, amount, reference, description='Customer payment'):
    cash = get_standard_account(branch, '1000')
    ar = get_standard_account(branch, '1100')
    return create_journal_entry(
        branch=branch,
        created_by=created_by,
        reference=reference,
        description=description,
        entry_date=date.today(),
        lines=[
            {'account': cash, 'line_type': 'debit', 'amount': amount},
            {'account': ar, 'line_type': 'credit', 'amount': amount},
        ],
    )


def record_customer_deposit(branch, created_by, amount, reference, description='Customer deposit'):
    cash = get_standard_account(branch, '1000')
    deposit = get_standard_account(branch, '1500')
    return create_journal_entry(
        branch=branch,
        created_by=created_by,
        reference=reference,
        description=description,
        entry_date=date.today(),
        lines=[
            {'account': cash, 'line_type': 'debit', 'amount': amount},
            {'account': deposit, 'line_type': 'credit', 'amount': amount},
        ],
    )


def record_customer_overpayment(branch, created_by, amount, reference, description='Customer overpayment'):
    cash = get_standard_account(branch, '1000')
    overpayment = get_standard_account(branch, '1510')
    return create_journal_entry(
        branch=branch,
        created_by=created_by,
        reference=reference,
        description=description,
        entry_date=date.today(),
        lines=[
            {'account': cash, 'line_type': 'debit', 'amount': amount},
            {'account': overpayment, 'line_type': 'credit', 'amount': amount},
        ],
    )


def apply_customer_deposit(branch, created_by, amount, reference, description='Apply customer deposit'):
    deposit = get_standard_account(branch, '1500')
    ar = get_standard_account(branch, '1100')
    return create_journal_entry(
        branch=branch,
        created_by=created_by,
        reference=reference,
        description=description,
        entry_date=date.today(),
        lines=[
            {'account': deposit, 'line_type': 'debit', 'amount': amount},
            {'account': ar, 'line_type': 'credit', 'amount': amount},
        ],
    )


def record_supplier_payment(branch, created_by, amount, reference, description='Supplier payment'):
    cash = get_standard_account(branch, '1000')
    ap = get_standard_account(branch, '2000')
    return create_journal_entry(
        branch=branch,
        created_by=created_by,
        reference=reference,
        description=description,
        entry_date=date.today(),
        lines=[
            {'account': cash, 'line_type': 'credit', 'amount': amount},
            {'account': ap, 'line_type': 'debit', 'amount': amount},
        ],
    )


def record_sale_revenue(branch, created_by, amount, reference, description='Sale revenue recognition'):
    ar = get_standard_account(branch, '1100')
    sales = get_standard_account(branch, '4000')
    return create_journal_entry(
        branch=branch,
        created_by=created_by,
        reference=reference,
        description=description,
        entry_date=date.today(),
        lines=[
            {'account': ar, 'line_type': 'debit', 'amount': amount},
            {'account': sales, 'line_type': 'credit', 'amount': amount},
        ],
    )


def record_inventory_purchase(branch, created_by, amount, reference, description='Inventory purchase'):
    inventory = get_standard_account(branch, '1200')
    ap = get_standard_account(branch, '2000')
    return create_journal_entry(
        branch=branch,
        created_by=created_by,
        reference=reference,
        description=description,
        entry_date=date.today(),
        lines=[
            {'account': inventory, 'line_type': 'debit', 'amount': amount},
            {'account': ap, 'line_type': 'credit', 'amount': amount},
        ],
    )


def record_refund(branch, created_by, amount, reference, description='Refund adjustment'):
    cash = get_standard_account(branch, '1000')
    sales = get_standard_account(branch, '4000')
    return create_journal_entry(
        branch=branch,
        created_by=created_by,
        reference=reference,
        description=description,
        entry_date=date.today(),
        lines=[
            {'account': sales, 'line_type': 'debit', 'amount': amount},
            {'account': cash, 'line_type': 'credit', 'amount': amount},
        ],
    )


def find_unbalanced_journal_entries(branch=None):
    queryset = JournalEntry.objects.filter(status='posted')
    if branch:
        queryset = queryset.filter(branch=branch)
    return [entry for entry in queryset if not entry.is_balanced]


def find_orphaned_journal_lines():
    return JournalLine.objects.filter(entry__isnull=True)


def _normalize_ledger_balance(branch=None, account_code=None, start_date=None, end_date=None):
    account = get_standard_account(branch, account_code)
    balance = get_account_balance(branch, account_code, start_date, end_date)
    if account.account_type in ['liability', 'equity', 'revenue']:
        return abs(balance)
    return balance


def _bucket_general_ledger_aging(account_code, branch=None, as_of_date=None):
    as_of_date = as_of_date or date.today()
    account = get_standard_account(branch, account_code)
    lines = JournalLine.objects.select_related('entry').filter(
        account=account,
        entry__status='posted',
        entry__entry_date__lte=as_of_date
    )
    if branch:
        lines = lines.filter(entry__branch=branch)

    aging = {
        'current': Decimal('0.00'),
        '30_days': Decimal('0.00'),
        '60_days': Decimal('0.00'),
        '90_days': Decimal('0.00'),
        'older': Decimal('0.00'),
    }

    grouped = {}
    for line in lines:
        source_key = (
            line.entry.source_document_type or 'unknown',
            line.entry.source_document_id or f'entry-{line.entry.id}'
        )
        entry_date = line.entry.entry_date or as_of_date
        if source_key not in grouped:
            grouped[source_key] = {
                'amount': Decimal('0.00'),
                'entry_date': entry_date,
            }

        if line.line_type == 'debit':
            grouped[source_key]['amount'] += line.amount
        else:
            grouped[source_key]['amount'] -= line.amount

        if entry_date < grouped[source_key]['entry_date']:
            grouped[source_key]['entry_date'] = entry_date

    for group in grouped.values():
        balance = group['amount']
        if account.account_type in ['liability', 'equity', 'revenue']:
            balance = -balance
        if balance <= 0:
            continue

        bucket_days = (as_of_date - group['entry_date']).days
        if bucket_days <= 30:
            aging['current'] += balance
        elif bucket_days <= 60:
            aging['30_days'] += balance
        elif bucket_days <= 90:
            aging['60_days'] += balance
        else:
            aging['older'] += balance

    ledger_balance = _normalize_ledger_balance(branch, account_code, end_date=as_of_date)
    return aging, ledger_balance


def get_account_balance(branch=None, account_code=None, start_date=None, end_date=None):
    lines = JournalLine.objects.select_related('account', 'entry').filter(entry__status='posted')
    if branch:
        lines = lines.filter(entry__branch=branch)
    if account_code:
        lines = lines.filter(account__code=account_code)
    if start_date:
        lines = lines.filter(entry__entry_date__gte=start_date)
    if end_date:
        lines = lines.filter(entry__entry_date__lte=end_date)

    debits = lines.filter(line_type='debit').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    credits = lines.filter(line_type='credit').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    return debits - credits


def compile_trial_balance(branch=None, start_date=None, end_date=None):
    accounts = Account.objects.all().order_by('code')
    if branch:
        accounts = accounts.filter(branch=branch)

    rows = []
    total_debits = Decimal('0.00')
    total_credits = Decimal('0.00')

    for account in accounts:
        lines = JournalLine.objects.filter(account=account, entry__status='posted')
        if start_date:
            lines = lines.filter(entry__entry_date__gte=start_date)
        if end_date:
            lines = lines.filter(entry__entry_date__lte=end_date)
        debit = lines.filter(line_type='debit').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        credit = lines.filter(line_type='credit').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        balance = debit - credit
        rows.append({
            'account_code': account.code,
            'account_name': account.name,
            'account_type': account.account_type,
            'debit': debit,
            'credit': credit,
            'balance': balance,
        })
        total_debits += debit
        total_credits += credit

    return {
        'rows': rows,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'is_balanced': total_debits == total_credits,
    }


def compile_general_ledger(branch=None, start_date=None, end_date=None):
    entries = JournalEntry.objects.filter(status='posted')
    if branch:
        entries = entries.filter(branch=branch)
    if start_date:
        entries = entries.filter(entry_date__gte=start_date)
    if end_date:
        entries = entries.filter(entry_date__lte=end_date)

    return [
        {
            'reference': entry.reference,
            'entry_date': entry.entry_date,
            'description': entry.description,
            'branch': entry.branch.name,
            'lines': [
                {
                    'account_code': line.account.code,
                    'account_name': line.account.name,
                    'line_type': line.line_type,
                    'amount': line.amount,
                    'description': line.description,
                }
                for line in entry.lines.all()
            ],
        }
        for entry in entries.order_by('entry_date', 'created_at')
    ]


def compile_balance_sheet(branch=None, start_date=None, end_date=None):
    trial_balance = compile_trial_balance(branch, start_date, end_date)
    assets = [row for row in trial_balance['rows'] if row['account_type'] in ['asset']]
    liabilities = [row for row in trial_balance['rows'] if row['account_type'] in ['liability']]
    equity = [row for row in trial_balance['rows'] if row['account_type'] in ['equity']]

    total_assets = sum(row['balance'] for row in assets)
    total_liabilities = sum(row['balance'] for row in liabilities)
    total_equity = sum(row['balance'] for row in equity)

    return {
        'assets': assets,
        'liabilities': liabilities,
        'equity': equity,
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'total_equity': total_equity,
        'is_balanced': total_assets == (total_liabilities + total_equity),
    }


def compile_profit_loss(branch=None, start_date=None, end_date=None):
    rows = []
    pl_accounts = Account.objects.filter(account_type__in=['revenue', 'cogs', 'expense'])
    if branch:
        pl_accounts = pl_accounts.filter(branch=branch)

    for account in pl_accounts:
        lines = JournalLine.objects.filter(account=account, entry__status='posted')
        if start_date:
            lines = lines.filter(entry__entry_date__gte=start_date)
        if end_date:
            lines = lines.filter(entry__entry_date__lte=end_date)
        debit = lines.filter(line_type='debit').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        credit = lines.filter(line_type='credit').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        if account.account_type == 'revenue':
            net = credit - debit
        else:
            net = debit - credit
        rows.append({
            'account_code': account.code,
            'account_name': account.name,
            'account_type': account.account_type,
            'debit': debit,
            'credit': credit,
            'net': net,
        })

    total_revenue = sum(row['net'] for row in rows if row['account_type'] == 'revenue')
    total_expenses = sum(row['net'] for row in rows if row['account_type'] in ['expense', 'cogs'])
    return {
        'rows': rows,
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'net_income': total_revenue - total_expenses,
    }


def compile_cash_flow(branch=None, start_date=None, end_date=None):
    cash_account = get_standard_account(branch, '1000')
    lines = JournalLine.objects.select_related('entry').filter(account=cash_account, entry__status='posted')
    if start_date:
        lines = lines.filter(entry__entry_date__gte=start_date)
    if end_date:
        lines = lines.filter(entry__entry_date__lte=end_date)

    cash_inflow = lines.filter(line_type='debit').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    cash_outflow = lines.filter(line_type='credit').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    net_cash_flow = cash_inflow - cash_outflow

    operating_cash_flow = Decimal('0.00')
    investing_cash_flow = Decimal('0.00')
    financing_cash_flow = Decimal('0.00')

    for entry in JournalEntry.objects.filter(lines__account=cash_account, status='posted').distinct():
        if start_date and entry.entry_date < start_date:
            continue
        if end_date and entry.entry_date > end_date:
            continue
        other_lines = entry.lines.exclude(account=cash_account)
        if other_lines.filter(account__account_type__in=['revenue', 'expense', 'cogs', 'asset', 'liability']).exists():
            operating_cash_flow += sum(
                line.amount if line.line_type == 'debit' else -line.amount
                for line in entry.lines.filter(account=cash_account)
            )
        elif other_lines.filter(account__account_type='equity').exists():
            financing_cash_flow += sum(
                line.amount if line.line_type == 'debit' else -line.amount
                for line in entry.lines.filter(account=cash_account)
            )
        else:
            investing_cash_flow += sum(
                line.amount if line.line_type == 'debit' else -line.amount
                for line in entry.lines.filter(account=cash_account)
            )

    return {
        'cash_account': cash_account.code,
        'opening_balance': get_account_balance(branch, cash_account.code, start_date=None, end_date=(start_date - timedelta(days=1)) if start_date else None),
        'closing_balance': get_account_balance(branch, cash_account.code, start_date=None, end_date=end_date),
        'cash_inflow': cash_inflow,
        'cash_outflow': cash_outflow,
        'net_cash_flow': net_cash_flow,
        'operating_cash_flow': operating_cash_flow,
        'investing_cash_flow': investing_cash_flow,
        'financing_cash_flow': financing_cash_flow,
    }


def compile_inventory_valuation(branch=None, as_of_date=None):
    from inventory.services import InventoryService

    as_of_date = as_of_date or date.today()
    ledger_value = _normalize_ledger_balance(branch, '1200', end_date=as_of_date)
    physical_inventory = InventoryService.get_inventory_valuation(branch)

    return {
        'ledger_inventory_value': ledger_value,
        'physical_inventory_value': physical_inventory['physical_value'],
        'valuation_method': physical_inventory.get('valuation_method', 'standard_cost'),
        'variance': ledger_value - physical_inventory['physical_value'],
        'as_of_date': as_of_date,
    }


def compile_accounts_receivable_aging(branch=None, as_of_date=None):
    as_of_date = as_of_date or date.today()
    aging, ledger_balance = _bucket_general_ledger_aging('1100', branch, as_of_date)

    return {
        'aging': aging,
        'ledger_balance': ledger_balance,
        'variance': ledger_balance - sum(aging.values()),
    }


def compile_accounts_payable_aging(branch=None, as_of_date=None):
    as_of_date = as_of_date or date.today()
    aging, ledger_balance = _bucket_general_ledger_aging('2000', branch, as_of_date)

    return {
        'aging': aging,
        'ledger_balance': ledger_balance,
        'variance': ledger_balance - sum(aging.values()),
    }


def get_period_start(period):
    today = date.today()
    if period == 'month':
        return today.replace(day=1)
    if period == 'quarter':
        quarter_start_month = ((today.month - 1) // 3) * 3 + 1
        return today.replace(month=quarter_start_month, day=1)
    if period == 'year':
        return today.replace(month=1, day=1)
    return None


def resolve_branch(branch_id):
    """Resolve query-string branch id to a Branch instance (or None)."""
    if branch_id in (None, ''):
        return None
    from branches.models import Branch
    try:
        return Branch.objects.get(pk=int(branch_id))
    except (Branch.DoesNotExist, ValueError, TypeError):
        return None


def calculate_pl_report(branch_id=None, period='month'):
    """
    Dashboard P&L report (orders, expenses, purchases) for the React Finance page.
    """
    from orders.models import Order, OrderItem
    from suppliers.models import Purchase

    branch = resolve_branch(branch_id)
    start = get_period_start(period)
    end = date.today()

    order_filter = Q(created_at__date__gte=start, created_at__date__lte=end)
    if branch:
        order_filter &= Q(branch=branch)

    orders = Order.objects.filter(order_filter)
    gross_sales = orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    discounts = orders.aggregate(total=Sum('discount_amount'))['total'] or Decimal('0.00')
    net_sales = gross_sales - discounts
    total_collected = orders.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    accounts_receivable = sum(
        max(Decimal('0.00'), (o.total_amount or Decimal('0.00')) - (o.amount_paid or Decimal('0.00')))
        for o in orders
    )

    order_ids = orders.values_list('id', flat=True)
    items = OrderItem.objects.filter(order_id__in=order_ids).select_related('variant')
    cogs = Decimal('0.00')
    for item in items:
        if item.variant and item.variant.cost_price:
            cogs += Decimal(str(item.variant.cost_price)) * Decimal(str(item.quantity))

    gross_profit = net_sales - cogs
    gross_margin_pct = (gross_profit / net_sales * 100) if net_sales > 0 else Decimal('0.00')

    exp_filter = Q(date__gte=start, date__lte=end)
    if branch:
        exp_filter &= Q(branch=branch)
    manual_expenses = Expense.objects.filter(exp_filter).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    expenses_by_category = list(
        Expense.objects.filter(exp_filter)
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )

    pur_filter = Q(purchase_date__gte=start, purchase_date__lte=end)
    if branch:
        pur_filter &= Q(branch=branch)
    supplier_payments = Purchase.objects.filter(pur_filter).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    supplier_outstanding = Purchase.objects.filter(pur_filter).aggregate(
        total=Sum(F('total_amount') - F('amount_paid'))
    )['total'] or Decimal('0.00')

    rev_filter = Q(date__gte=start, date__lte=end)
    if branch:
        rev_filter &= Q(branch=branch)
    manual_revenue = Revenue.objects.filter(rev_filter).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    total_revenue = net_sales + manual_revenue
    total_expenses = manual_expenses + supplier_payments
    net_profit = total_revenue - cogs - total_expenses
    net_margin_pct = (net_profit / total_revenue * 100) if total_revenue > 0 else Decimal('0.00')

    trend = []
    for i in range(5, -1, -1):
        month_end = (end.replace(day=1) - timedelta(days=1)) if i == 0 else end
        # walk back i months from current month start
        month_start = end.replace(day=1)
        for _ in range(i):
            month_start = (month_start - timedelta(days=1)).replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_end = next_month - timedelta(days=1)

        m_order_filter = Q(created_at__date__gte=month_start, created_at__date__lte=month_end)
        m_exp_filter = Q(date__gte=month_start, date__lte=month_end)
        if branch:
            m_order_filter &= Q(branch=branch)
            m_exp_filter &= Q(branch=branch)

        m_revenue = Order.objects.filter(m_order_filter).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        m_expenses = Expense.objects.filter(m_exp_filter).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        trend.append({
            'month': month_start.strftime('%b %Y'),
            'revenue': float(m_revenue),
            'expenses': float(m_expenses),
            'profit': float(m_revenue - m_expenses),
        })

    return {
        'period_start': start.isoformat() if start else None,
        'period_end': end.isoformat(),
        'sales': {
            'gross_sales': gross_sales,
            'discounts': discounts,
            'net_sales': net_sales,
            'total_collected': total_collected,
            'accounts_receivable': accounts_receivable,
            'manual_revenue': manual_revenue,
            'total_revenue': total_revenue,
            'order_count': orders.count(),
        },
        'cogs': cogs,
        'gross_profit': gross_profit,
        'gross_margin_pct': float(gross_margin_pct),
        'expenses': {
            'manual': manual_expenses,
            'supplier_payments': supplier_payments,
            'supplier_outstanding': supplier_outstanding,
            'total': total_expenses,
            'by_category': expenses_by_category,
        },
        'net_profit': net_profit,
        'net_margin_pct': float(net_margin_pct),
        'trend': trend,
    }


def calculate_gl_report(branch_id=None, period='month'):
    """GL-based report bundle (trial balance / cash flow / aging)."""
    branch = resolve_branch(branch_id)
    start = get_period_start(period)
    end = date.today()
    report = compile_profit_loss(branch=branch, start_date=start, end_date=end)
    cash_flow = compile_cash_flow(branch=branch, start_date=start, end_date=end)
    inventory_valuation = compile_inventory_valuation(branch=branch, as_of_date=end)
    ar_aging = compile_accounts_receivable_aging(branch=branch, as_of_date=end)
    ap_aging = compile_accounts_payable_aging(branch=branch, as_of_date=end)

    return {
        'period_start': start,
        'period_end': end,
        'profit_loss': report,
        'cash_flow': cash_flow,
        'inventory_valuation': inventory_valuation,
        'accounts_receivable_aging': ar_aging,
        'accounts_payable_aging': ap_aging,
    }


def close_year_end(period, created_by=None):
    if period.end_date.month != 12:
        raise ValidationError('Year-end close must be performed on a year-ending accounting period.')
    return close_accounting_period(period, created_by=created_by)


def get_period_cash_position(branch, as_of_date=None):
    as_of_date = as_of_date or date.today()
    cash_account = get_standard_account(branch, '1000')
    cash_balance = get_account_balance(branch, cash_account.code, end_date=as_of_date)
    return {
        'cash_balance': cash_balance,
        'as_of_date': as_of_date,
    }


def run_nightly_reconciliation(branch=None, as_of_date=None):
    from .reconciliation import ReconciliationService
    from .models import ReconciliationRun

    as_of_date = as_of_date or date.today()
    results = ReconciliationService.run_full_reconciliation(branch, as_of_date, persist=True)
    return results
