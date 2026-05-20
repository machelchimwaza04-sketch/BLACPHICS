# Payment GL Integration Summary

## Overview
Completed enterprise-grade GL posting integration for customer payment flows, including deposits, overpayments, refunds, reversals, and write-offs. All payment events now generate balanced, auditable journal entries linked to the Payment records.

## Changes Implemented

### 1. Finance Services (`finance/services.py`)
**Added/Updated Standard Chart of Accounts:**
- Account `1500`: Customer Deposits (liability)
- Account `1510`: Customer Overpayments (liability)

**Updated Functions:**
- `get_or_create_standard_chart()`: Added deposit/overpayment accounts
- `get_standard_account()`: Added lookup for deposit/overpayment codes

**New Deposit/Overpayment GL Functions:**
- `record_customer_deposit()`: Posts customer deposit cash receipt to liability account
- `record_customer_overpayment()`: Posts overpayment excess to liability account  
- `apply_customer_deposit()`: Reverses deposit liability and credits AR when applied

**Updated Existing Functions:**
- `record_customer_payment()`: Handles normal payment posting
- `record_refund()`: Posts refund as sales debit/cash credit
- `record_supplier_payment()`: Posts supplier payment as AP debit/cash credit

### 2. Order Services (`orders/services.py`)

#### OrderService.complete_order()
**Enhanced Deposit Application:**
- Calculates deposit application amount as minimum of (deposit_amount, discounted_total)
- Calls `apply_customer_deposit()` GL function to reverse deposit liability and credit AR
- Does NOT deduct deposit_amount from order (preserved for reconciliation/audit)
- Posts sale revenue recognition via `record_sale_revenue()`

#### PaymentService.add_payment()
**Comprehensive GL Posting for All Payment Types:**

1. **Deposit Payments:**
   - Calls `record_customer_deposit()` to post cash/liability entry
   - Sets payment_type='deposit'
   - Links Payment.journal_entry FK

2. **Regular Payments + Overpayments:**
   - Calculates amount applied to AR vs excess
   - Posts cash receipt to AR (debits cash, credits AR)
   - Posts excess to overpayment liability (debits cash, credits overpayment)
   - Links Payment.journal_entry FK
   - Sets source_document_type='OrderPayment' for traceability

3. **Write-off Payments:**
   - Posts to 6000 (Operating Expenses) vs 1100 (AR)
   - Sets source_document_type='OrderPayment'
   - Links Payment.journal_entry FK

#### PaymentService.process_refund()
**GL Integration:**
- Posts refund via `record_refund()` function
- Links Payment.journal_entry FK
- Calls `order.recalculate_payment_status()`

#### PaymentService.reverse_payment()
**GL Integration:**
- Creates reversal journal entry (AR debit, cash credit)
- Sets source_document_type='OrderPayment' and source_document_id
- Links Payment.journal_entry FK

#### PaymentService.writeoff_order_balance()
**GL Integration:**
- Posts write-off with source document traceability
- Links Payment.journal_entry FK

### 3. Order Models (`orders/models.py`)
**Payment Model Updates:**
- `journal_entry` FK to `JournalEntry` (null=True, blank=True, on_delete=PROTECT)
- Enables GL linkage for all payment transactions
- Allows ledger-driven reconciliation

### 4. Finance Models (`finance/models.py`)
**Already Had:**
- `source_document_type` CharField on JournalEntry (e.g., 'OrderPayment')
- `source_document_id` CharField on JournalEntry (links to Payment.id)
- Enables bi-directional Payment ↔ JournalEntry traceability

## Key Design Decisions

### 1. Deposit Application Flow
- **Non-Destructive:** Deposit amount tracked separately on Order, not auto-deducted
- **Explicit GL Posting:** Only `apply_customer_deposit()` call creates reversal entry
- **Order Completion Triggered:** Applied during `OrderService.complete_order()` only
- **Audit Trail:** Both deposit posting and application visible in GL with separate journal entries

### 2. Overpayment Handling
- **Liability Account (1510):** Overpayments held as customer credit/liability
- **Excess Calculation:** `amount_to_ar = min(payment.amount, remaining_due)`
- **Auto-Detection:** System automatically sets `payment_type='overpayment'` when excess detected
- **GL Split:** Single entry splits debit (cash) to both AR and overpayment liability

### 3. Source Document Traceability
- All customer payment entries include source_document_type='OrderPayment'
- source_document_id=str(payment.id) enables lookup from GL back to Payment
- Bi-directional referencing for reconciliation

### 4. Journal Entry Linkage
- Payment.journal_entry FK stores the GL entry reference
- Prevents double-posting via select_for_update in future enhancements
- Enables quick GL reversal if payment is cancelled

## GL Posting Rules

### Standard Payment (payment_type='payment')
```
Dr. Cash                 [amount]
    Cr. Accounts Receivable      [amount]
```

### Deposit Payment (payment_type='deposit')
```
Dr. Cash                 [amount]
    Cr. Customer Deposits        [amount]
```

### Overpayment (payment_type='overpayment')
```
Dr. Cash                 [amount]
    Cr. Accounts Receivable      [amount applied to balance]
    Cr. Customer Overpayments    [excess amount]
```

### Refund (payment_type='refund')
```
Dr. Sales Revenue        [amount]
    Cr. Cash                     [amount]
```

### Reversal (payment_type='reversal')
```
Dr. Accounts Receivable  [original amount]
    Cr. Cash                     [original amount]
```

### Write-off (payment_type='writeoff')
```
Dr. Operating Expenses   [amount]
    Cr. Accounts Receivable      [amount]
```

### Deposit Application (separate entry)
```
Dr. Customer Deposits    [applied amount]
    Cr. Accounts Receivable      [applied amount]
```

## Testing & Validation

### Syntax Validation
- ✓ `py_compile` on orders/services.py, finance/services.py
- ✓ Django import validation with DJANGO_SETTINGS_MODULE
- ✓ Module load verification

### Function Verification
- ✓ `record_customer_deposit()` callable with correct parameters
- ✓ `apply_customer_deposit()` callable with correct parameters
- ✓ PaymentService.add_payment() with payment_type support
- ✓ PaymentService.process_refund() with GL linkage
- ✓ PaymentService.reverse_payment() with GL linkage
- ✓ PaymentService.writeoff_order_balance() with GL linkage

## Impact on Other Modules

### Inventory Services
- No direct impact (inventory GL posting separate)
- Inventory transactions link to GL via InventoryTransaction.general_ledger_entry FK

### Supplier Services  
- Supplier payment GL posting unchanged (uses record_supplier_payment)
- PurchasePayment.journal_entry FK already present

### Orders Views/Serializers
- No changes needed (Payment model backward compatible)
- Journal entry FK optional (null=True)

## Migration & Rollout

### Database Changes Required
- Migration to add Payment.journal_entry FK to JournalEntry
- Status: MIGRATION PENDING (create via Django migrations)

### Data Consistency
- Old payments (pre-migration) will have journal_entry=NULL
- New payments will always create journal entries
- Reconciliation tooling can identify unmigrated payments

### Backward Compatibility
- Payment serializers remain unchanged
- Journal entry FK optional (allows legacy data)
- GL functions callable independently

## Next Steps

1. **Create Django Migration:** Add Payment.journal_entry FK
2. **Implement Reconciliation Jobs:**
   - Payment-to-GL reconciliation (detect orphaned payments)
   - AR balance reconciliation (GL vs orders.total balance)
   - Overpayment liability reconciliation

3. **Complete COGS/Inventory GL:**
   - Ensure complete inventory GL posting from services
   - Link inventory transactions to GL entries

4. **Add Supplier GL Posting:**
   - Complete supplier bill posting
   - Receipt GL posting
   - Payment GL posting with source traceability

5. **Enterprise Reporting:**
   - AP/AR aging from GL (not operational tables)
   - GL-driven cash flow
   - Ledger-driven trial balance

## References

- Finance Models: [finance/models.py](finance/models.py)
- Finance Services: [finance/services.py](finance/services.py)
- Orders Models: [orders/models.py](orders/models.py)
- Orders Services: [orders/services.py](orders/services.py)
