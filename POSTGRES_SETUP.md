# PostgreSQL Migration Guide

## Option 1: Local PostgreSQL Installation (Windows)

### Step 1: Install PostgreSQL
- Download: https://www.postgresql.org/download/windows/
- Run installer, choose default settings
- Remember password for `postgres` user (default user)
- Default port: `5432`

### Step 2: Create Database
Open PostgreSQL command line (pgAdmin or psql):
```sql
CREATE DATABASE blacphics_db OWNER postgres;
```

### Step 3: Set Environment Variables
Create `.env` file in project root:
```
DATABASE_URL=postgres://postgres:PASSWORD@localhost:5432/blacphics_db
```
(Replace `PASSWORD` with the password you set during installation)

### Step 4: Install Dependencies
```bash
env\Scripts\pip install -r requirements.txt
```

### Step 5: Run Migrations
```bash
env\Scripts\python manage.py migrate
```

### Step 6: Test Connection
```bash
env\Scripts\python manage.py dbshell
```
If successful, you'll see the PostgreSQL prompt.

---

## Option 2: Docker PostgreSQL (Recommended for Development)

### Step 1: Install Docker
- Download: https://www.docker.com/products/docker-desktop

### Step 2: Start PostgreSQL in Docker
```bash
docker run --name blacphics-postgres `
  -e POSTGRES_USER=postgres `
  -e POSTGRES_PASSWORD=postgres `
  -e POSTGRES_DB=blacphics_db `
  -p 5432:5432 `
  -d postgres:15
```

### Step 3: Set Environment Variable
Create `.env` file:
```
DATABASE_URL=postgres://postgres:postgres@localhost:5432/blacphics_db
```

### Step 4: Install Dependencies & Run Migrations
```bash
env\Scripts\pip install -r requirements.txt
env\Scripts\python manage.py migrate
```

### Step 5: Stop/Start Container
```bash
# Stop
docker stop blacphics-postgres

# Start
docker start blacphics-postgres

# Remove
docker rm blacphics-postgres
```

---

## Migrating Data from SQLite to PostgreSQL

Run the migration script:
```bash
env\Scripts\python migrate_sqlite_to_postgres.py
```

This will:
1. Dump all data from SQLite
2. Create necessary PostgreSQL sequences
3. Load data into PostgreSQL
4. Verify data integrity

---

## Verification

Run the QA harness to verify PostgreSQL works:
```bash
env\Scripts\python qa/system_test.py
```

All tests should pass with PostgreSQL backend.

---

## Rollback to SQLite

If you need to switch back:
1. Remove `DATABASE_URL` from `.env`
2. Restart Django
3. Django will use SQLite `db.sqlite3`

---

## Troubleshooting

### Connection refused
- Check if PostgreSQL is running
- Verify port 5432 is open
- Check credentials in `DATABASE_URL`

### Permission denied on `postgres` user
- On Windows: Run Command Prompt as Administrator
- On Docker: Check container logs: `docker logs blacphics-postgres`

### Foreign key constraint errors
- Temporarily disable: `env\Scripts\python manage.py migrate --disable-integrity-check`

### Sequences out of sync
- Run: `env\Scripts\python manage.py sqlsequencereset` to fix

