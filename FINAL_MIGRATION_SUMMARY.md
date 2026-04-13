# Final migration summary — Sprint 6 hardened

This document records the restored “service + selector” architecture after the directory move.

## Backend

- **`Blacphics/`** project package restored (`settings`, `urls`, ASGI/WSGI) with `django-cors-headers`, DRF, SQLite defaults.
- **`common.branch_scope`**: `BranchScopedQuerysetMixin` applied to branch-scoped viewsets where appropriate.
- **Orders**: `OrderService.transition_to_completed` replaces ad-hoc stock logic on `Order.complete_order()` (signals + line-item handlers own inventory).
- **Finance**: `get_pl_report_payload` in `finance/selectors.py`; exports reuse the same payload; `DailyPLSnapshot` + `pl_service` for optional daily rollups.
- **Suppliers**: `PurchaseService` for payments and receive inventory; signals fire stock **once** on transition into `received`.
- **Products / orders**: selector modules for optimized query patterns.

## Frontend

- **`src/features/`**: `finance/` (`FinancePage`, `useFinanceData`), `pos/`, `inventory/` (Products + Alerts via re-exports).
- **`src/shared/api/client.js`**: shared Axios instance with consistent error handling.
- **`src/api/api.js`**: API helpers using the shared client (Vite proxies `/api` to Django).

## Dependencies

See `requirements.txt` (Django 6, DRF, CORS, openpyxl, Pillow, reportlab).
