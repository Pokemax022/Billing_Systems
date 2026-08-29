# CCTV Pro — Quotation, Billing & Profit Analytics Platform

A production-ready Flask application designed for CCTV installation and security solutions businesses to generate quotations, manage invoices, record payments, calculate GST, track profitability, and share documents over WhatsApp.

---

## 🏗 Target Architecture

```text
User Browser / Mobile Client
          ↓
Online Flask Web Application (Gunicorn / WSGI)
          ↓
SQLAlchemy 2.0 (Connection Pooling & Keep-Alive)
          ↓
Online PostgreSQL Database (Supabase / Neon / Render / Railway / PythonAnywhere)
```

* **Production Database**: PostgreSQL (configured via `DATABASE_URL` environment variable).
* **Local Development**: Automatic fallback to SQLite (`instance/cctv_software.db`) if `DATABASE_URL` is omitted.

---

## 🚀 Quick Start (Local Development)

### Windows (PowerShell / Command Prompt)

1. **Activate Virtual Environment**:
   ```cmd
   venv\Scripts\activate
   ```
2. **Install Dependencies**:
   ```cmd
   pip install -r requirements.txt
   ```
3. **Run Application**:
   ```cmd
   python app.py
   ```
   Or double-click `run.bat`.
4. Open your browser at: **`http://localhost:5001`**
   - **Default Username:** `admin`
   - **Default Password:** `admin123`

---

## 🗄 Online PostgreSQL Setup & Configuration

### 1. Obtain a PostgreSQL Database
You can use any cloud PostgreSQL provider:
* **Supabase** (Free Tier): [https://supabase.com](https://supabase.com)
* **Neon Tech** (Serverless Free Tier): [https://neon.tech](https://neon.tech)
* **Render Postgres**: [https://render.com](https://render.com)
* **Railway**: [https://railway.app](https://railway.app)
* **Aiven**: [https://aiven.io](https://aiven.io)

### 2. Configure Environment Variables
Create a `.env` file in the root directory (copy from `.env.example`):

```env
FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=generate-a-strong-random-secret-key-here
DATABASE_URL=postgresql://username:password@host:5432/database
```

> **Note:** Legacy `postgres://` connection strings (used by Render/Railway/Heroku) are automatically converted to `postgresql://` for SQLAlchemy 2.0+ and psycopg compatibility.

---

## 🔄 SQLite → PostgreSQL Data Migration

A lossless data migration pipeline is provided in `scripts/migrate_sqlite_to_postgres.py`.

### Step 1: Perform a Dry Run (Verify SQLite data & counts)
```bash
python scripts/migrate_sqlite_to_postgres.py --dry-run
```

### Step 2: Migrate All Data to PostgreSQL
```bash
python scripts/migrate_sqlite_to_postgres.py --postgres-url "postgresql://username:password@host:5432/database"
```
Or if `DATABASE_URL` is set in your `.env`:
```bash
python scripts/migrate_sqlite_to_postgres.py
```

### What the Migration Tool Does:
1. Discovers all 13 SQLite tables (`user`, `company_settings`, `customer`, `product`, `quotation`, `invoice`, etc.).
2. Creates the PostgreSQL schema matching SQLAlchemy models.
3. Migrates data in topological dependency order (no foreign key violations).
4. Sanitizes and parses dates/datetimes and numeric types.
5. Updates PostgreSQL auto-increment sequences (`setval`) to match migrated IDs.
6. Performs a row-by-row count comparison and prints a verification summary.
7. Leaves the original SQLite database file completely untouched.

---

## 📦 Database Migrations (Flask-Migrate / Alembic)

To apply future schema changes:

1. **Create a migration script**:
   ```bash
   flask --app app.py db migrate -m "Description of change"
   ```
2. **Apply migration to database**:
   ```bash
   flask --app app.py db upgrade
   ```
3. **Check current database revision**:
   ```bash
   flask --app app.py db current
   ```

---

## 🌐 Production Deployment Guides

### 1. Render / Railway / Koyeb
* **Build Command:**
  ```bash
  pip install -r requirements.txt && playwright install chromium --with-deps
  ```
* **Start Command:**
  ```bash
  gunicorn "app:create_app()" --workers 4 --timeout 120 --bind 0.0.0.0:$PORT
  ```
  *(or `gunicorn app:app --workers 4 --timeout 120 --bind 0.0.0.0:$PORT`)*
* **Environment Variables:**
  - `DATABASE_URL` = `postgresql://...`
  - `SECRET_KEY` = `<strong-secret>`
  - `FLASK_ENV` = `production`

---

### 2. PythonAnywhere Deployment
1. Open the **Web** tab in PythonAnywhere dashboard and click **Add a new web app** (choose Manual Configuration, Python 3.10+).
2. Open a **Bash Console** and clone/upload your project:
   ```bash
   cd ~
   git clone <your-repo-url> cctv_software
   cd cctv_software
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Edit the **WSGI configuration file** (link in PythonAnywhere Web tab):
   ```python
   import sys
   import os
   from dotenv import load_dotenv

   # Path to project directory
   project_home = '/home/<your-username>/cctv_software'
   if project_home not in sys.path:
       sys.path.insert(0, project_home)

   # Load environment variables
   load_dotenv(os.path.join(project_home, '.env'))

   from app import app as application
   ```
4. Set the **Virtualenv** path in PythonAnywhere Web tab to:
   `/home/<your-username>/cctv_software/venv`
5. Click **Reload <your-app>.pythonanywhere.com**.

---

## 🧪 Running Automated Tests

Run the full test suite (12 test suites covering authentication, CRUD, calculations, APIs, export, and error handlers):

```bash
python tests/test_app.py
```
Or:
```bash
python -m unittest discover tests
```

---

## 🔒 Security & Best Practices

* **Zero Hardcoded Secrets**: Secrets and database credentials are read exclusively from environment variables.
* **Connection Pooling**: PostgreSQL connections use `pool_pre_ping=True` and `pool_recycle=300` to prevent dropouts on hosted cloud providers.
* **Safe Error Handling**: Custom 400, 403, 404, and 500 pages prevent leaking technical stack traces or database connection strings.
* **CSRF Protection**: All form submissions are protected via Flask-WTF CSRF tokens.
