# Build &amp; environment fixes

## Python

Use a virtual environment and install backend dependencies:

```text
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -U pip
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

If `python -m pip` fails, install pip for your Python install or use the Python version that already has pip on your machine.

## Frontend (Vite)

From `frontend/`:

```text
npm install
npm run dev
```

`vite.config.js` proxies `/api` to `http://127.0.0.1:8000`.

### Common issues

- **`vite` is not recognized**: run `npm install` so `node_modules/.bin` is populated; use `npx vite build` if needed.
- **Network errors during `npm install`**: retry, or switch registry / check firewall; on Windows, close editors locking `node_modules` if you see `EPERM` during cleanup.

## Git

After restoring files:

```text
git add .
git status
git commit -m "RESTORE: Full architectural restoration to Sprint 6 state"
```

Use `git push origin main --force` only when you intend to rewrite remote history.
