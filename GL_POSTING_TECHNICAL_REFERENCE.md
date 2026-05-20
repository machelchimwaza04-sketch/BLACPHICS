# GL Posting Technical Reference

## Quick Start: Adding a New GL Posting Point

### Pattern 1: Simple Transaction
```python
# In your service.py:
from finance import services as finance_services

def my_transaction(branch, amount, created_by, reference):
    journal_entry = finance_services.create_journal_entry(
        branch=branch,
        created_by=created_by,
        reference=reference,
        description="My transaction description",
        entry_date=timezone.now().date(),
        lines=[
            {'account': account1, 'line_type': 'debit', 'amount': amount},
            {'account': account2, 'line_type': 'credit', 'amount': amount},
        ],
        source_document_type='MyDocumentType',
        source_document_id=str(my_record.id),
    )
    return journal_entry
```

### Pattern 2: Linking to Model
```python
# In your model:
class MyPayment(models.Model):
    # ... other fields ...
    journal_entry = models.ForeignKey(
        'finance.JournalEntry',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='my_payments'
    )

# In your service:
payment = MyPayment.objects.create(...)
payment.journal_entry = journal_entry
payment.save(update_fields=['journal_entry'])
```

### Pattern 3: Conditional GL Posting
```python
if payment_type == 'deposit':
    journal_entry = finance_services.record_customer_deposit(...)
elif payment_type == 'payment':
    # Calculate split between AR and overpayment
    amount_to_ar = min(payment.amount, remaining_due)
    excess = payment.amount - amount_to_ar
    lines = [
        {'account': cash, 'line_type': 'debit', 'amount': payment.amount},
        {'account': ar, 'line_type': 'credit', 'amount': amount_to_ar},
    ]
    if excess > 0:
        lines.append({'account': overpayment, 'line_type': 'credit', 'amount': excess})
    journal_entry = finance_services.create_journal_entry(
        branch=branch,
        created_by=created_by,
        reference=reference,
        description=description,
        entry_date=timezone.now().date(),
        lines=lines,
        source_document_type='OrderPayment',
        source_document_id=str(payment.id),
    )
```

## Account Codes Reference

### Assets
- `1000`: Cash/Bank
- `1100`: Accounts Receivable
- `1200`: Inventory Asset
- `1300`: Prepayments
- `1400`: Tax Receivable

### Liabilities
- `1500`: Customer Deposits (liability - unusual!)
- `1510`: Customer Overpayments (liability - unusual!)
- `2000`: Accounts Payable
- `2100`: Accrued Expenses
- `2200`: Tax Payable

### Equity
- `3000`: Equity
- `3010`: Retained Earnings
- `3100`: Current Year Earnings

### Revenue
- `4000`: Sales Revenue
- `4010`: Sales Discounts
- `4100`: Other Revenue

### COGS/Expenses
- `5000`: Cost of Goods Sold
- `5100`: Purchase Discounts
- `5200`: Inventory Adjustments
- `6000`: Operating Expenses
- `6100`: Bad Debt Expense
- `6200`: Inventory Shrinkage

## Getting Accounts

```python
from finance.services import get_standard_account

# Get an account (creates if doesn't exist)
cash = get_standard_account(branch, '1000')
ar = get_standard_account(branch, '1100')

# Account properties
print(cash.code)           # '1000'
print(cash.name)           # 'Cash/Bank'
print(cash.account_type)   # 'asset'
print(cash.branch)         # <Branch object>
print(cash.balance)        # Not directly - use get_account_balance()
```

## GL Balance Queries

```python
from finance.services import get_account_balance, compile_trial_balance

# Get single account balance
balance = get_account_balance(
    branch=branch,
    account_code='1000',
    start_date=start_date,
    end_date=end_date
)

# Get all accounts balance (trial balance)
tb = compile_trial_balance(
    branch=branch,
    start_date=start_date,
    end_date=end_date
)
for row in tb['rows']:
    print(f"{row['account_code']}: {row['balance']}")
```

## Common GL Posting Combinations

### Customer Payment (Normal)
**Scenario:** Customer pays $100 toward $120 order
```
Dr. 1000 (Cash)           $100
    Cr. 1100 (AR)                $100
```

### Customer Payment (Overpayment)
**Scenario:** Customer pays $150 toward $120 order
```
Dr. 1000 (Cash)           $150
    Cr. 1100 (AR)                $120
    Cr. 1510 (Overpayment)       $30
```

### Deposit Receipt
**Scenario:** Customer deposits $50 for future purchase
```
Dr. 1000 (Cash)           $50
    Cr. 1500 (Deposits)          $50
```

### Apply Deposit to Order
**Scenario:** Apply $50 deposit to $120 order
```
Dr. 1500 (Deposits)       $50
    Cr. 1100 (AR)                $50
```

### Refund
**Scenario:** Refund $30
```
Dr. 4000 (Sales)          $30
    Cr. 1000 (Cash)              $30
```

### Write-off
**Scenario:** Write off $20 uncollectible
```
Dr. 6100 (Bad Debt)       $20
    Cr. 1100 (AR)                $20
```

### Supplier Payment
**Scenario:** Pay supplier $500 on $500 bill
```
Dr. 2000 (AP)             $500
    Cr. 1000 (Cash)              $500
```

### Supplier Bill Receipt
**Scenario:** Receive $400 inventory from supplier
```
Dr. 1200 (Inventory)      $400
    Cr. 2000 (AP)                $400
```

### Sale Recognition
**Scenario:** Recognize $100 sale revenue
```
Dr. 1100 (AR)             $100
    Cr. 4000 (Sales)             $100
```

### COGS Recognition
**Scenario:** Recognize $60 COGS when $100 sale delivered
```
Dr. 5000 (COGS)           $60
    Cr. 1200 (Inventory)         $60
```

## Debugging GL Issues

### 1. Unbalanced Entry Error
```python
# Check what causes the error:
from finance.models import JournalEntry
entry = JournalEntry.objects.get(reference='REF-123')
print(f"Is balanced: {entry.is_balanced}")
print(f"Debit total: {entry.total_debits}")
print(f"Credit total: {entry.total_credits}")

# Find all unbalanced entries:
from finance.services import find_unbalanced_journal_entries
unbalanced = find_unbalanced_journal_entries(branch=branch)
```

### 2. Missing GL Entry After Payment
```python
# Check if payment created GL entry:
from orders.models import Payment
payment = Payment.objects.get(id=123)
if payment.journal_entry is None:
    print("ERROR: No GL entry linked!")
else:
    print(f"GL Entry: {payment.journal_entry.reference}")
    print(f"Lines: {payment.journal_entry.lines.count()}")
```

### 3. Verify Account Balance
```python
# Get specific account balance
from finance.services import get_account_balance
from finance.models import Account

account = Account.objects.get(code='1000', branch=branch)
balance = get_account_balance(branch=branch, account_code='1000')
print(f"Cash Balance: {balance}")

# Manually calculate from GL:
from django.db.models import Sum
from finance.models import JournalLine
lines = JournalLine.objects.filter(
    account=account,
    entry__status='posted'
)
debits = lines.filter(line_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0
credits = lines.filter(line_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0
print(f"Manual calc: {debits - credits}")
```

### 4. Find Orphaned Records
```python
# Payments without GL entries:
from orders.models import Payment
orphaned = Payment.objects.filter(journal_entry__isnull=True)
print(f"Orphaned payments: {orphaned.count()}")

# GL entries without source documents:
from finance.models import JournalEntry
unlinked = JournalEntry.objects.filter(source_document_type='', source_document_id='')
print(f"Unlinked GL entries: {unlinked.count()}")
```

## Transaction Safety

### Atomic GL Posting
```python
from django.db import transaction

with transaction.atomic():
    # Payment created
    payment = Payment.objects.create(...)
    
    # GL entry created
    journal_entry = finance_services.create_journal_entry(...)
    
    # Linked
    payment.journal_entry = journal_entry
    payment.save(update_fields=['journal_entry'])
    
    # If any step fails, entire transaction rolls back
```

### Future: Prevent Concurrent Updates
```python
# To be added - prevents concurrent payment processing:
with transaction.atomic():
    order = Order.objects.select_for_update().get(id=order_id)
    payment = Payment.objects.create(order=order, ...)
    journal_entry = finance_services.create_journal_entry(...)
```

## Reconciliation Helpers

### AR Reconciliation Query
```python
from django.db.models import Sum
from orders.models import Order
from finance.services import get_account_balance

# From operational tables
total_ar_operational = Order.objects.filter(
    status='completed',
    branch=branch
).aggregate(total=Sum('balance_due'))['total'] or 0

# From GL
total_ar_gl = get_account_balance(branch=branch, account_code='1100')

print(f"AR Operational: {total_ar_operational}")
print(f"AR GL: {total_ar_gl}")
print(f"Variance: {total_ar_operational - total_ar_gl}")
```

### Cash Reconciliation Query
```python
# From GL
cash_gl = get_account_balance(branch=branch, account_code='1000')

# From operational (should match after GL posting)
from orders.models import Payment
from suppliers.models import PurchasePayment
customer_payments = Payment.objects.filter(
    branch=branch
).aggregate(total=Sum('amount'))['total'] or 0

print(f"Cash GL: {cash_gl}")
print(f"Customer payments: {customer_payments}")
```

## Best Practices

1. **Always use get_standard_account()** - don't hardcode account lookups
2. **Always set source_document_type/id** - enables traceability
3. **Always link model FK** - enables bi-directional queries
4. **Always use transaction.atomic()** - payment+GL are atomic
5. **Always validate is_balanced** - catch double-entry violations early
6. **Always set post=True** (default) - marks entry as posted immediately
7. **Use entry_date parameter** - don't assume today's date
8. **Document account split logic** - especially for deposits/overpayments

## Common Pitfalls

❌ **DON'T:**
- Create GL entries without linking to source document
- Use hardcoded account codes instead of get_standard_account()
- Skip transaction.atomic() wrapping
- Create unbalanced entries
- Assume account balances exist (always filter)
- Mix positive/negative amounts (use line_type instead)

✅ **DO:**
- Always create GL for financial transactions
- Link Payment.journal_entry FK
- Wrap in transaction.atomic()
- Validate is_balanced before posting
- Use source_document_type for audit trail
- Use consistent date handling (timezone.now().date())

## References

- Finance Models: [finance/models.py](finance/models.py)
- Finance Services: [finance/services.py](finance/services.py)
- Payment GL Integration: [PAYMENT_GL_INTEGRATION_SUMMARY.md](PAYMENT_GL_INTEGRATION_SUMMARY.md)
- Next Tasks: [NEXT_PRIORITY_TASKS.md](NEXT_PRIORITY_TASKS.md)
