# Blacphics architecture (Sprint 6)

## Layout

- **Django project package**: `Blacphics/` (`settings.py`, `urls.py`, `wsgi.py`).
- **Apps** (flat, project root): `branches`, `customers`, `products`, `orders`, `suppliers`, `finance`, plus **`common`** for cross-cutting API helpers.
- **Frontend** (`frontend/src/`): feature folders under `features/` (`finance`, `pos`, `inventory`), shared Axios client in `shared/api/client.js`, legacy `pages/` re-exported where useful.

## Backend layers

| Concern | Location | Role |
|--------|----------|------|
| **Branch scope** | `common/branch_scope.py` | `BranchScopedQuerysetMixin`, `parse_branch_id`, `ensure_branch_scope` (for future auth). |
| **Selectors** | `*/selectors.py` | Read-optimized querysets and report payloads (`finance.selectors.get_pl_report_payload`). |
| **Services** | `*/services/` | Writes and transitions (`orders.services.order_service.OrderService`, `suppliers.services.purchase_service.PurchaseService`). |
| **Signals** | `orders/signals.py`, `suppliers/signals.py` | Stock and purchase lifecycle; supplier receive is **idempotent** (inventory only when status first becomes `received`). |

## P&amp;L snapshots

- Model: `finance.models.DailyPLSnapshot` (optional daily rollups).
- Builder: `finance.services.pl_service.calculate_daily_snapshot` (for cron/management commands).
- Live API still uses `get_pl_report_payload` for the interactive report.

## Frontend

- **Routes** in `App.jsx` import feature entry points (`features/finance/FinancePage`, `features/pos/POSPage`, etc.).
- **API** calls go through `shared/api/client.js` (central error toasts); explicit `branch` query params remain in `api.js` helpers.

## How to add a feature

1. Create selectors for reads; service module for multi-step writes.
2. Keep viewsets thin: mixin for branch filter + call selector/service.
3. Add a `frontend/src/features/<name>/` module with the page and optional `use*Data.js` hook.
