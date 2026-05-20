# Inventory Transaction & Ledger System

## Overview

A production-grade inventory management system for Blacphics POS that provides complete audit trails, double-entry accounting, and real-time stock tracking. The system ensures data integrity, prevents stock discrepancies, and provides comprehensive reporting capabilities.

## Core Components

### 1. Inventory Transactions
**Purpose**: Records every stock movement with complete audit trail
- **Transaction Types**: Purchase receipts, sales, adjustments, transfers, returns, damage
- **Atomic Operations**: All stock changes are transactional
- **Unique Numbering**: Branch-date sequential numbering (INV-BRANCH-YYYYMMDD-XXXX)
- **Status Tracking**: Pending → Completed workflow

### 2. Double-Entry Ledger
**Purpose**: Accounting system for inventory value tracking
- **Debit/Credit System**: Proper accounting entries for all transactions
- **Account Types**: Inventory Asset, COGS Expense, Adjustments, etc.
- **Valuation Support**: FIFO, LIFO, Average Cost methods
- **Financial Reporting**: Complete inventory accounting

### 3. Stock Adjustments
**Purpose**: Manual corrections with approval workflow
- **Adjustment Types**: Physical counts, damage, theft, corrections
- **Approval Workflow**: Draft → Pending → Approved → Completed
- **Value Impact Tracking**: Financial impact of adjustments
- **Audit Trail**: Complete history of changes

### 4. Inventory Snapshots
**Purpose**: Periodic stock reconciliation
- **Snapshot Types**: Daily, weekly, monthly, manual
- **Variance Analysis**: Compare system vs physical counts
- **Reconciliation Reports**: Identify discrepancies
- **Historical Tracking**: Stock levels over time

## Architecture

### Models

#### InventoryTransaction
```python
class InventoryTransaction(models.Model):
    branch = models.ForeignKey(Branch)
    transaction_type = models.CharField(choices=TRANSACTION_TYPES)
    transaction_number = models.CharField(unique=True)  # Auto-generated
    product = models.ForeignKey(Product)
    variant = models.ForeignKey(ProductVariant, null=True)
    quantity_change = models.IntegerField()  # + for in, - for out
    unit_cost = models.DecimalField()
    unit_price = models.DecimalField()
    status = models.CharField(choices=STATUS_CHOICES)
    # Audit fields...
```

#### InventoryLedger
```python
class InventoryLedger(models.Model):
    transaction = models.ForeignKey(InventoryTransaction)
    entry_type = models.CharField(choices=[('debit', 'credit')])
    account_type = models.CharField(choices=ACCOUNT_TYPES)
    amount = models.DecimalField()
    # Reference fields...
```

#### StockAdjustment
```python
class StockAdjustment(models.Model):
    branch = models.ForeignKey(Branch)
    adjustment_type = models.CharField(choices=ADJUSTMENT_TYPES)
    product = models.ForeignKey(Product)
    system_quantity = models.PositiveIntegerField()
    actual_quantity = models.PositiveIntegerField()
    adjustment_quantity = models.IntegerField()  # actual - system
    status = models.CharField(choices=STATUS_CHOICES)
    # Approval workflow fields...
```

### Service Layer

#### InventoryService
Centralized business logic handling:

- **Stock Management**: Atomic stock level updates with concurrency control
- **Transaction Processing**: Create transactions with ledger entries
- **Adjustment Workflow**: Process stock corrections
- **Snapshot Creation**: Generate inventory snapshots
- **Reporting**: Valuation, turnover, analytics

```python
class InventoryService:
    @staticmethod
    def create_inventory_transaction(branch, transaction_type, ...):
        # Create transaction + update stock + create ledger entries

    @staticmethod
    def process_stock_adjustment(adjustment, user):
        # Validate + create transaction + update status

    @staticmethod
    def create_inventory_snapshot(branch, snapshot_type, ...):
        # Generate comprehensive snapshot
```

## API Endpoints

### Transaction Management
```
GET    /api/inventory/transactions/          # List transactions
GET    /api/inventory/transactions/{id}/     # Transaction details
GET    /api/inventory/transactions/summary/  # Transaction summary

POST   /api/inventory/transactions/create/   # Create transaction (service)
```

### Ledger
```
GET    /api/inventory/ledger/                 # List ledger entries
GET    /api/inventory/ledger/account_summary/ # Account balances
```

### Adjustments
```
GET    /api/inventory/adjustments/            # List adjustments
POST   /api/inventory/adjustments/            # Create adjustment
POST   /api/inventory/adjustments/{id}/approve/    # Approve
POST   /api/inventory/adjustments/{id}/complete/   # Complete
```

### Snapshots
```
GET    /api/inventory/snapshots/              # List snapshots
POST   /api/inventory/snapshots/create/       # Create snapshot
GET    /api/inventory/snapshots/{id}/variance_report/  # Variance analysis
```

### Reports
```
GET    /api/inventory/reports/valuation/      # Inventory valuation
GET    /api/inventory/reports/turnover/       # Turnover analysis
GET    /api/inventory/reports/stock_status/   # Stock status summary
GET    /api/inventory/reports/transaction_summary/  # Transaction analysis
```

## Business Rules

### Stock Management
- **Atomic Updates**: All stock changes use `select_for_update()`
- **Reservation System**: Separate available vs committed quantities
- **Validation**: Prevent negative stock levels
- **Branch Isolation**: Stock operations scoped to branch

### Transaction Types
- **Purchase Receipt**: +quantity, debit inventory asset
- **Sale**: -quantity, debit COGS, credit inventory asset
- **Adjustment**: ±quantity based on correction type
- **Transfer**: Inter-branch stock movements
- **Return/Damage**: -quantity with specific accounting

### Approval Workflow
- **Auto-approval**: Small adjustments (< $100 impact)
- **Manual Approval**: Large adjustments, damage, theft
- **Role-based**: Managers and admins can approve
- **Audit Trail**: Complete approval history

## Integration Points

### Order System
- **Order Confirmation**: Reserve stock for custom orders
- **Order Completion**: Create sale transactions, deduct stock
- **Order Cancellation**: Release reserved stock

### Purchase System
- **Purchase Receipt**: Create receipt transactions, add stock
- **Partial Receipts**: Handle partial delivery scenarios

### Product System
- **Stock Updates**: Sync with product/variant stock fields
- **Low Stock Alerts**: Integration with alerting system

## Reporting & Analytics

### Inventory Valuation
- **Methods**: FIFO, LIFO, Average Cost
- **Real-time**: Current inventory value
- **Historical**: Value at specific dates

### Turnover Analysis
- **Ratio Calculation**: COGS / Average Inventory
- **Period Analysis**: Daily, weekly, monthly
- **Trend Tracking**: Turnover over time

### Stock Status
- **Summary**: Total products, in stock, low stock, out of stock
- **By Category**: Breakdown by product categories
- **By Branch**: Multi-branch analysis

## Security & Permissions

### Branch Isolation
- All queries filtered by user's branch
- Cross-branch operations prevented
- Branch-scoped admin interface

### Role-based Access
- **Cashiers**: View transactions, create basic adjustments
- **Managers**: Approve adjustments, create snapshots
- **Admins**: Full system access

### Audit Trail
- All changes tracked with user and timestamp
- Immutable transaction history
- Complete adjustment workflow log

## Performance Considerations

### Database Optimization
- **Indexes**: Optimized for common queries
- **Partitioning**: Branch-based partitioning for scale
- **Archiving**: Old transactions can be archived

### Caching Strategy
- **Stock Levels**: Redis caching for hot products
- **Valuation**: Cached valuation calculations
- **Reports**: Pre-calculated report data

### Concurrency Control
- **Row Locking**: `select_for_update()` for stock operations
- **Optimistic Locking**: Version fields for conflict detection
- **Queue Processing**: Async processing for bulk operations

## Implementation Guide

### Setup
```bash
# 1. Create inventory app
python manage.py startapp inventory

# 2. Add to INSTALLED_APPS
INSTALLED_APPS = [
    # ... existing apps
    'inventory',
]

# 3. Create migrations
python manage.py makemigrations inventory
python manage.py migrate

# 4. Include URLs
path('api/inventory/', include('inventory.urls')),
```

### Usage Examples

#### Create Stock Adjustment
```python
from inventory.services import InventoryService

adjustment = InventoryService.create_stock_adjustment(
    branch=branch,
    adjustment_type='physical_count',
    product=product,
    system_quantity=100,
    actual_quantity=95,
    unit_cost=Decimal('5.00'),
    created_by=user,
    reason="Monthly physical count"
)
```

#### Process Order Completion
```python
# Automatically handled by signals, or manually:
from inventory.services import InventoryService

transactions = InventoryService.process_order_completion(order, user)
```

#### Generate Inventory Snapshot
```python
snapshot = InventoryService.create_inventory_snapshot(
    branch=branch,
    snapshot_type='monthly',
    created_by=user,
    physical_counts=physical_count_data
)
```

## Testing Strategy

### Unit Tests
- Service layer functionality
- Model validation
- Business rule enforcement

### Integration Tests
- Order completion flow
- Purchase receipt processing
- Adjustment workflow

### Concurrency Tests
- Race condition prevention
- Atomic operation validation
- High-load simulation

### Key Test Scenarios
```python
def test_concurrent_stock_updates():
    # Verify atomic stock operations under load

def test_adjustment_approval_workflow():
    # Test complete approval process

def test_inventory_valuation_accuracy():
    # Verify valuation calculations
```

## Monitoring & Alerting

### Key Metrics
- Transaction processing success rate
- Stock discrepancy alerts
- Adjustment approval times
- Inventory turnover trends

### Alerts
- Low stock warnings
- Large adjustments pending approval
- Stock discrepancies in snapshots
- Failed transaction processing

## Future Enhancements

### Advanced Features
- **Multi-location**: Warehouse management
- **Lot Tracking**: Batch/lot number tracking
- **Serial Numbers**: Individual item tracking
- **Quality Control**: Inspection workflows

### Performance
- **Real-time Dashboards**: Live inventory metrics
- **Predictive Analytics**: Demand forecasting
- **Automated Reordering**: Low stock triggers

### Integration
- **Barcode Scanning**: Mobile inventory counts
- **IoT Sensors**: Automated stock monitoring
- **Third-party ERP**: External system integration

This inventory system provides enterprise-grade stock management with complete audit trails, financial accounting, and operational efficiency for retail operations.