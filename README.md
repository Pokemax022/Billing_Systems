# CCTV Pro — Quotation, Billing & Profit Analytics Platform

A production-ready Flask application designed for CCTV installation and security solutions businesses to generate quotations, manage invoices, record payments, calculate GST, track profitability, and share documents over WhatsApp.

---

## 🏗 System Architecture

```text
Browser / Mobile Client
          ↓
Vercel Serverless Function (Python 3.10+ WSGI)
          ↓
Flask Application + Jinja2 Templates
          ↓
SQLAlchemy 2.0 (Connection Pooling & Keep-Alive)
          ↓
Supabase PostgreSQL Database (IPv4 Pooler - Mumbai)
```

* **Production Database**: Online Supabase PostgreSQL (configured via `DATABASE_URL`).
* **Deployment Platform**: Vercel Serverless (`api/index.py` & `vercel.json`).
* **Local Development**: Automatic fallback to SQLite (`instance/cctv_software.db`) or local `.env` with Supabase PostgreSQL.

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

## ⚡ Vercel Deployment Guide

### Step 1: Push Code to GitHub
Ensure the project is committed and pushed to your GitHub repository:
```bash
git add .
git commit -m "Configure Vercel serverless deployment"
git push origin main
```

### Step 2: Import Project into Vercel
1. Log in to [Vercel Dashboard](https://vercel.com).
2. Click **"Add New..."** → **"Project"**.
3. Select your GitHub repository: **`Pokemax022/Billing_Systems`**.
4. Framework Preset: **Other** (Vercel automatically detects `vercel.json` and `@vercel/python`).
5. Root Directory: `./` (default).

### Step 3: Configure Environment Variables in Vercel
In the **Environment Variables** section of the Vercel project setup, add:

| Key | Example Value | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres.knqqknvcehjugnmrzrzk:PASSWORD@aws-0-ap-south-1.pooler.supabase.com:5432/postgres?sslmode=require` | Supabase PostgreSQL Connection String (URL-encoded password) |
| `SECRET_KEY` | `your-secure-random-32-byte-secret-key` | Flask Session Secret Key |
| `FLASK_ENV` | `production` | Enables production mode & security headers |

### Step 4: Click Deploy
Vercel will build the serverless Python functions and deploy your application worldwide.

---

## 🔄 SQLite → Supabase PostgreSQL Data Migration

A lossless migration pipeline is provided in `scripts/migrate_sqlite_to_postgres.py`.

### Dry Run (Verify SQLite counts without writing):
```bash
python scripts/migrate_sqlite_to_postgres.py --dry-run
```

### Execute Migration to Supabase:
```bash
python scripts/migrate_sqlite_to_postgres.py
```

### What the Migration Tool Does:
1. Discovers all 13 SQLite tables (`user`, `company_settings`, `customer`, `product`, `quotation`, `invoice`, etc.).
2. Creates PostgreSQL schemas matching SQLAlchemy models.
3. Migrates data in topological dependency order (zero foreign-key violations).
4. Sanitizes and parses dates/datetimes and numeric types.
5. Updates PostgreSQL auto-increment sequences (`setval`) to match migrated IDs.
6. Performs a row-by-row count comparison and prints a verification summary.
7. Leaves the original SQLite database file completely untouched.

---

## 📄 PDF Generation & Playwright Notes

- **Quotation & Invoice Browser Previews**: Rendered instantly in high-definition HTML with dynamic UPI payment QR codes.
- **Client-Side Printing / PDF**: Users can click "Print / Save PDF" in browser previews for pixel-perfect PDF export via browser print engine (`Ctrl + P`).
- **Serverless Storage**: Temporary PDFs and upload files use `/tmp/pdf` and `/tmp/excel_import` to operate smoothly within Vercel's serverless execution environment.

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
* **Connection Pooling**: PostgreSQL connections use `pool_pre_ping=True`, `pool_recycle=300`, and TCP keepalives to prevent dropouts on Supabase.
* **Safe Error Handling**: Custom 400, 403, 404, and 500 handlers prevent leaking technical stack traces.
* **CSRF Protection**: All form submissions are protected via Flask-WTF CSRF tokens.
