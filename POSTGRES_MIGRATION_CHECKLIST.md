# PostgreSQL Migration Checklist

Use this checklist to migrate from SQLite to PostgreSQL safely.

## Pre-Migration (5 min)

- [ ] Backup current SQLite database
  ```bash
  copy db.sqlite3 db.sqlite3.backup
  ```

- [ ] Stop Django development server
  ```
  Press Ctrl+C in terminal
  ```

- [ ] Verify no active migrations pending
  ```bash
  env\Scripts\python manage.py showmigrations
  ```

## PostgreSQL Setup (10-20 min)

### Option A: Docker (Recommended)

- [ ] Docker Desktop is installed
- [ ] Run docker helper
  ```bash
  postgres_docker.bat start
  ```
- [ ] Copy `DATABASE_URL` from output to `.env` file

### Option B: Local PostgreSQL

- [ ] PostgreSQL installed locally
- [ ] Database `blacphics_db` created
- [ ] Create `.env` file with:
  ```
  DATABASE_URL=postgres://postgres:YOUR_PASSWORD@localhost:5432/blacphics_db
  ```

## Dependency Installation (5 min)

- [ ] Install new dependencies
  ```bash
  env\Scripts\pip install -r requirements.txt
  ```

- [ ] Verify installation
  ```bash
  env\Scripts\pip list | findstr psycopg2
  ```

## Data Migration (5 min)

- [ ] Run migration script
  ```bash
  env\Scripts\python migrate_sqlite_to_postgres.py
  ```

- [ ] Check output for success message

## Verification (10 min)

- [ ] Test database connection
  ```bash
  env\Scripts\python manage.py dbshell
  ```
  Should show `postgres=#>` prompt

- [ ] Run QA harness
  ```bash
  env\Scripts\python qa/system_test.py
  ```
  All tests should PASS

- [ ] Start development server
  ```bash
  env\Scripts\python manage.py runserver 127.0.0.1:8000
  ```

- [ ] Test API endpoints in browser
  - http://localhost:8000/api/products/
  - http://localhost:8000/api/orders/

## Post-Migration

- [ ] Archive SQLite backup
  ```bash
  ren db.sqlite3.backup db.sqlite3.backup.old
  ```

- [ ] Update deployment docs to use PostgreSQL

- [ ] Monitor logs for any issues

- [ ] Keep SQLite backup for 7 days before deletion

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "connection refused" | Check PostgreSQL is running (`postgres_docker.bat status`) |
| "database does not exist" | Create it: `postgres_docker.bat start` |
| "authentication failed" | Check DATABASE_URL in `.env` file |
| "psycopg2 not found" | Run `pip install -r requirements.txt` again |
| "foreign key errors" | Run migration script again, or check data integrity |

## Rollback Plan (if needed)

If migration fails:
1. Stop Django server
2. Remove `DATABASE_URL` from `.env`
3. Restart server → will use SQLite again
4. Restore from backup: `copy db.sqlite3.backup db.sqlite3`
5. Restart server

## Performance Baseline After Migration

After successful migration, run performance test:

```bash
env\Scripts\python qa/system_test.py
```

Expected latencies with PostgreSQL:
- Product list: ~150-200ms (vs ~180ms on SQLite)
- Order list: ~20-30ms (vs ~25ms)
- Order creation: ~10-20ms (vs ~15ms)

These should be similar or slightly better.

---

**Estimated total time: 45 minutes**

If you encounter issues, check `POSTGRES_SETUP.md` for detailed troubleshooting.
