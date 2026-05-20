# Enterprise GL Integration - Next Priority Tasks

## Immediate (This Sprint)

### 1. Create Django Migration for Payment GL Linkage
**File:** `orders/migrations/0007_payment_journal_entry.py`
**Action:** 
```python
# Add ForeignKey to Payment model
field = models.ForeignKey('finance.JournalEntry', on_delete=models.PROTECT, 
                         null=True, blank=True, related_name='order_payments')
```
**Rationale:** Enables Payment ↔ JournalEntry bi-directional traceability

### 2. Implement Payment-to-GL Reconciliation Test
**File:** `orders/tests_service.py` or `finance/tests.py`
**Tests Needed:**
- Verify each payment type creates correct GL entry
- Verify journal_entry FK is populated on Payment save
- Verify deposit application creates separate GL entry
- Verify refund GL posting reverses sales revenue
- Verify overpayment splits correctly between AR and liability

### 3. Complete Order Completion GL Flow
**File:** `orders/services.py::OrderService.complete_order()`
**Verify:**
- ✓ Deposit application posting (already implemented)
- ✓ Sale revenue recognition (already implemented)
- ✓ COGS posting (CHECK: may need InventoryService integration)
- Missing: Inventory valuation GL entry if using FIFO/average cost

**Action:** Test complete_order() with a paid order containing deposits

### 4. Document GL Posting Checklist for Audit
**File:** Create `GL_POSTING_CHECKLIST.md`
**Content:**
- [ ] All customer payments linked to JournalEntry
- [ ] All refunds linked to JournalEntry
- [ ] All write-offs linked to JournalEntry
- [ ] All deposits linked to JournalEntry
- [ ] All overpayments posted to liability account
- [ ] All deposit applications posted when order completes
- [ ] AR/GL balance reconciles
- [ ] Cash/GL balance reconciles
- [ ] GL is balanced (debits = credits)

## Short Term (Next 2 Weeks)

### 5. Implement Complete Supplier GL Integration
**Current State:** `record_supplier_payment()` exists but incomplete
**Missing:**
- [ ] Supplier bill receipt GL posting (inventory + AP)
- [ ] Link PurchasePayment to JournalEntry (already has FK)
- [ ] Support for partial payments
- [ ] Overpayment handling (vendor credits)

**Files to Update:**
- `suppliers/services.py`
- `suppliers/models.py` (verify journal_entry FK)

### 6. Add COGS GL Posting from Inventory
**Current State:** InventoryService has GL linkage but COGS posting incomplete
**Required:**
- [ ] Post COGS entry when inventory is consumed (order completion)
- [ ] Use FIFO/weighted average valuation
- [ ] Link to sales transaction via InventoryTransaction.general_ledger_entry

**Files:**
- `inventory/services.py::process_order_completion()`

### 7. Reconciliation Service
**New File:** `finance/reconciliation.py`
**Functions:**
```python
def reconcile_ar_balance(branch, as_of_date)
def reconcile_ap_balance(branch, as_of_date)
def reconcile_cash_balance(branch, as_of_date)
def reconcile_gl_to_operational(branch)
def find_orphaned_payments()  # Payments without GL entries
def find_unlinked_gl_entries()  # GL entries without source document
```

### 8. GL-Driven Financial Reports
**Replace operational table queries with GL:**
- `accounts_receivable_aging()` - from GL, not orders table
- `accounts_payable_aging()` - from GL, not suppliers table
- `cash_flow_statement()` - from GL cash account
- `trial_balance()` - already GL-based, verify correct

### 9. Add GL Posting Audit Log
**Enhancement to JournalEntry:**
- Add `posted_timestamp` field
- Add `posted_by` user field
- Add `posting_notes` for audit trail
- Create JournalEntryAuditLog model for versioning

## Medium Term (Next Month)

### 10. Enterprise Deposit Management
**Features:**
- [ ] Track customer lifetime deposits
- [ ] Auto-apply deposits to new orders
- [ ] Deposit refund request workflow
- [ ] Deposit expiry rules (if applicable)
- [ ] GL reconciliation of deposit liability

### 11. Multi-Currency Support
**GL Enhancement:**
- [ ] Add currency code to JournalEntry
- [ ] Add exchange rate tracking
- [ ] Implement revaluation entries for period-end

### 12. Accounting Period Enforcement
**Current:** Period exists but not enforced
**Required:**
- [ ] Prevent posting to closed periods
- [ ] Support period reopening (with audit trail)
- [ ] Year-end close workflow
- [ ] Retained earnings rollforward

### 13. GL Export & Compliance
**Features:**
- [ ] Export GL to CSV/Excel format
- [ ] JSON export for audit tools
- [ ] Support for accounting software import (Xero, QuickBooks format)
- [ ] IFRS/GAAP compliance validation

## Backlog (Future Quarters)

- [ ] Bank reconciliation module
- [ ] Advanced GL queries (drill-down capability)
- [ ] Variance analysis (budget vs actual)
- [ ] Cash management forecasting
- [ ] Multi-entity consolidation
- [ ] Intercompany transaction elimination

---

## Definition of Done for Payment GL Integration

✅ COMPLETE:
- ✓ Deposit/overpayment GL accounts created (1500, 1510)
- ✓ Payment GL posting functions implemented
- ✓ OrderService deposit application GL posting
- ✓ PaymentService GL entry creation for all payment types
- ✓ Payment model journal_entry FK added
- ✓ Code syntax validation passed
- ✓ Module import verification passed

⏳ PENDING:
- [ ] Django migration created
- [ ] Integration tests written
- [ ] Manual test with real order flow
- [ ] Reconciliation validation

---

## Risk Assessment

### High Risk (Address ASAP)
- **Risk:** Payments created before migration will have journal_entry=NULL
  - **Mitigation:** Create data migration to backfill or flag for manual review
  
- **Risk:** Concurrent payment processing could create duplicate GL entries
  - **Mitigation:** Add select_for_update() to PaymentService methods

- **Risk:** GL posting failure leaves payment record orphaned
  - **Mitigation:** Wrap in transaction.atomic() (already done) + add retry logic

### Medium Risk
- **Risk:** Deposit amount tracking could diverge from GL if application fails
  - **Mitigation:** Add reconciliation job to detect divergence
  
- **Risk:** Report queries inefficient with large GL volume
  - **Mitigation:** Add GL aggregate materialization (summary tables)

### Low Risk
- **Risk:** Serializer changes needed for frontend
  - **Status:** Not needed (journal_entry FK optional)
  
- **Risk:** Backward compatibility with legacy payments
  - **Status:** Handled (NULL is allowed)
