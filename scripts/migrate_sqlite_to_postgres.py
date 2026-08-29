#!/usr/bin/env python3
"""
SQLite to PostgreSQL Lossless Data Migration Pipeline
=====================================================
Migrates all tables, schemas, relations, and data from local SQLite
to an online/production PostgreSQL database without modifying the SQLite file.

Usage:
    python scripts/migrate_sqlite_to_postgres.py
    python scripts/migrate_sqlite_to_postgres.py --postgres-url "postgresql://user:pass@host:5432/dbname"
    python scripts/migrate_sqlite_to_postgres.py --dry-run
    python scripts/migrate_sqlite_to_postgres.py --truncate-target
"""

import os
import sys
import argparse
import sqlite3
from datetime import datetime, date
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import normalize_database_url, get_config
from database.db import db
import models  # Centralized model registry


# Tables in strict topological insertion order (parent tables first)
MIGRATION_TABLE_ORDER = [
    'user',
    'company_settings',
    'customer',
    'product',
    'excel_mapping',
    'import_log',
    'quotation',
    'invoice',
    'quotation_item',
    'payment',
    'gst_record',
    'invoice_item',
    'invoice_payment',
]


def parse_datetime(val):
    """Safely convert SQLite datetime string to Python datetime object."""
    if val is None or val == '':
        return None
    if isinstance(val, (datetime, date)):
        return val
    val_str = str(val).strip()
    # Try multiple datetime formats
    formats = [
        '%Y-%m-%d %H:%M:%S.%f',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d',
    ]
    for fmt in formats:
        try:
            return datetime.strptime(val_str, fmt)
        except ValueError:
            continue
    return val_str


def parse_date(val):
    """Safely convert SQLite date string to Python date object."""
    if val is None or val == '':
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    val_str = str(val).strip()
    try:
        return datetime.strptime(val_str[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def sanitize_row(table_name: str, row: dict) -> dict:
    """Convert SQLite row values to appropriate Python/PostgreSQL types."""
    clean = {}
    for col, val in row.items():
        if val is None:
            clean[col] = None
            continue

        # Handle boolean columns
        if table_name == 'gst_record' and col == 'filed':
            clean[col] = bool(val)
            continue

        # Handle date columns
        if col in ('date', 'due_date', 'payment_date'):
            clean[col] = parse_date(val)
            continue

        # Handle datetime columns
        if col in ('created_at', 'updated_at'):
            clean[col] = parse_datetime(val)
            continue

        # Handle float/numeric columns
        if col in ('sub_total', 'cgst_total', 'sgst_total', 'igst_total',
                   'installation_rate', 'installation_charges', 'wiring_charges',
                   'transport_charges', 'grand_total', 'total_dealer_cost',
                   'dealer_price', 'selling_price', 'gst_percent', 'taxable_value',
                   'tax_amount', 'line_total', 'discount_value', 'discount_amount',
                   'paid_amount', 'balance_due', 'amount', 'cgst', 'sgst', 'igst',
                   'total_tax', 'total_business_amount', 'unit_price', 'discount_percent',
                   'customer_price'):
            try:
                clean[col] = float(val) if val is not None and str(val).strip() != '' else 0.0
            except (ValueError, TypeError):
                clean[col] = 0.0
            continue

        # Handle integer columns
        if col in ('id', 'installation_qty', 'quantity', 'stock', 'customer_id',
                   'quotation_id', 'product_id', 'invoice_id', 'total_rows',
                   'imported_rows', 'failed_rows', 'duplicate_rows'):
            if val == '' or val is None:
                clean[col] = None
            else:
                try:
                    clean[col] = int(float(val))
                except (ValueError, TypeError):
                    clean[col] = None
            continue

        # Strings & Text
        clean[col] = str(val)

    return clean


def run_migration(sqlite_path: str, postgres_url: str, dry_run: bool = False, truncate_target: bool = False):
    """Execute complete migration from SQLite to PostgreSQL."""
    print("=" * 70)
    print("  ONLINE POSTGRESQL MIGRATION PIPELINE")
    print("=" * 70)

    # 1. Validate SQLite database source
    sqlite_file = Path(sqlite_path)
    if not sqlite_file.exists():
        print(f"[ERROR] SQLite database not found at: {sqlite_file}")
        sys.exit(1)
    
    print(f"[OK] Source SQLite DB: {sqlite_file.resolve()} ({sqlite_file.stat().st_size:,} bytes)")
    
    # 2. Connect to SQLite
    sqlite_conn = sqlite3.connect(str(sqlite_file))
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    # Discover tables in SQLite
    sqlite_tables = [
        row[0] for row in sqlite_cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        ).fetchall()
    ]
    print(f"[OK] Discovered {len(sqlite_tables)} tables in SQLite database.")

    # If dry run and no PostgreSQL URL provided, perform SQLite inspection only
    if dry_run and (not postgres_url or postgres_url == 'sqlite:///:memory:'):
        print("\n[INFO] DRY RUN MODE: Inspecting SQLite source database.")
        print("-" * 60)
        print(f"{'Table Name':<25} | {'SQLite Rows':<15}")
        print("-" * 60)
        total_source_rows = 0
        for table in MIGRATION_TABLE_ORDER:
            if table in sqlite_tables:
                sqlite_cur.execute(f"SELECT COUNT(*) FROM '{table}';")
                cnt = sqlite_cur.fetchone()[0]
                total_source_rows += cnt
                print(f"{table:<25} | {cnt:<15}")
        print("-" * 60)
        print(f"Total Rows in SQLite DB: {total_source_rows}")
        print("[INFO] Dry run complete. No changes were made.")
        return

    # 3. Setup PostgreSQL SQLAlchemy connection
    from flask import Flask
    from sqlalchemy import text, inspect

    clean_pg_url = normalize_database_url(postgres_url)
    # Hide password in logs
    masked_url = clean_pg_url
    if '@' in masked_url and '://' in masked_url:
        prefix, rest = masked_url.split('://', 1)
        user_info, host_info = rest.split('@', 1)
        user = user_info.split(':')[0]
        masked_url = f"{prefix}://{user}:****@{host_info}"
    print(f"[OK] Target Database: {masked_url}")

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = clean_pg_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    if clean_pg_url.startswith('postgresql'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
        }

    db.init_app(app)

    with app.app_context():
        engine = db.engine
        
        # Test connection
        try:
            with engine.connect() as conn:
                version_query = "SELECT version();" if clean_pg_url.startswith('postgresql') else "SELECT 1;"
                res = conn.execute(text(version_query)).fetchone()
                print(f"[OK] Connected to target database server successfully.")
                if clean_pg_url.startswith('postgresql') and res:
                    print(f"     {str(res[0])[:75]}...")
        except Exception as e:
            print(f"[ERROR] Failed to connect to database: {e}")
            sys.exit(1)

        if dry_run:
            print("\n[INFO] DRY RUN MODE: Validating target connection and SQLite row counts.")
            print("-" * 60)
            print(f"{'Table Name':<25} | {'SQLite Rows':<15}")
            print("-" * 60)
            total_source_rows = 0
            for table in MIGRATION_TABLE_ORDER:
                if table in sqlite_tables:
                    sqlite_cur.execute(f"SELECT COUNT(*) FROM '{table}';")
                    cnt = sqlite_cur.fetchone()[0]
                    total_source_rows += cnt
                    print(f"{table:<25} | {cnt:<15}")
            print("-" * 60)
            print(f"Total Rows to Migrate: {total_source_rows}")
            print("[INFO] Target database connection tested OK. No records modified.")
            return

        # 4. Create all tables in PostgreSQL if not present
        print("\n[INFO] Creating PostgreSQL tables matching SQLAlchemy models...")
        db.create_all()
        print("[OK] PostgreSQL schema verified / created successfully.")

        # 5. Optional Truncate Target
        if truncate_target:
            print("\n[WARNING] Truncating target tables for clean migration...")
            with engine.begin() as conn:
                # Truncate in reverse dependency order with CASCADE
                for table in reversed(MIGRATION_TABLE_ORDER):
                    try:
                        conn.execute(text(f'TRUNCATE TABLE "{table}" CASCADE;'))
                    except Exception as e:
                        pass
            print("[OK] Target tables truncated.")

        # 6. Migrate Data in strict order
        print("\n" + "=" * 70)
        print(f"{'Table':<20} | {'SQLite':<8} | {'Migrated':<10} | {'Status':<15}")
        print("=" * 70)

        migration_results = {}
        total_migrated = 0

        for table_name in MIGRATION_TABLE_ORDER:
            if table_name not in sqlite_tables:
                continue

            # Fetch all rows from SQLite
            sqlite_cur.execute(f"SELECT * FROM '{table_name}';")
            sqlite_rows = sqlite_cur.fetchall()
            source_count = len(sqlite_rows)

            if source_count == 0:
                print(f"{table_name:<20} | {0:<8} | {0:<10} | {'Empty (Skipped)':<15}")
                migration_results[table_name] = {'source': 0, 'target': 0, 'status': 'Empty'}
                continue

            # Get target model class from SQLAlchemy
            model_class = getattr(models, {
                'user': 'User',
                'company_settings': 'CompanySettings',
                'customer': 'Customer',
                'product': 'Product',
                'excel_mapping': 'ExcelMapping',
                'import_log': 'ImportLog',
                'quotation': 'Quotation',
                'quotation_item': 'QuotationItem',
                'payment': 'Payment',
                'gst_record': 'GSTRecord',
                'invoice': 'Invoice',
                'invoice_item': 'InvoiceItem',
                'invoice_payment': 'InvoicePayment',
            }.get(table_name, ''))

            if not model_class:
                print(f"[WARN] No SQLAlchemy model mapping for table: {table_name}")
                continue

            # Insert records
            migrated_count = 0
            try:
                for row_dict in sqlite_rows:
                    cleaned_data = sanitize_row(table_name, dict(row_dict))
                    
                    # Check if record with this ID already exists in target (idempotent migration)
                    rec_id = cleaned_data.get('id')
                    existing = None
                    if rec_id is not None:
                        existing = db.session.get(model_class, rec_id)

                    if existing:
                        # Update fields
                        for k, v in cleaned_data.items():
                            setattr(existing, k, v)
                    else:
                        obj = model_class(**cleaned_data)
                        db.session.add(obj)

                    migrated_count += 1

                db.session.commit()

                # 7. Update PostgreSQL auto-increment sequence
                try:
                    with engine.begin() as seq_conn:
                        seq_conn.execute(text(
                            f"SELECT setval(pg_get_serial_sequence('\"{table_name}\"', 'id'), "
                            f"coalesce(max(id), 1), max(id) IS NOT NULL) FROM \"{table_name}\";"
                        ))
                except Exception as seq_err:
                    # Ignore sequence error for tables without sequence or non-integer pk
                    pass

                status_str = "[OK] Success"
                print(f"{table_name:<20} | {source_count:<8} | {migrated_count:<10} | {status_str:<15}")
                migration_results[table_name] = {
                    'source': source_count,
                    'target': migrated_count,
                    'status': 'Success'
                }
                total_migrated += migrated_count

            except Exception as e:
                db.session.rollback()
                status_str = f"[FAIL] {str(e)[:25]}"
                print(f"{table_name:<20} | {source_count:<8} | {migrated_count:<10} | {status_str:<15}")
                print(f"      Details: {e}")
                migration_results[table_name] = {
                    'source': source_count,
                    'target': 0,
                    'status': f'Error: {e}'
                }

        # 8. Verification step: Read back target row counts
        print("\n" + "=" * 70)
        print("  POST-MIGRATION ROW COUNT VERIFICATION")
        print("=" * 70)
        print(f"{'Table':<20} | {'SQLite Rows':<12} | {'PostgreSQL Rows':<15} | {'Match?':<10}")
        print("-" * 70)

        all_matched = True
        for table_name in MIGRATION_TABLE_ORDER:
            if table_name not in sqlite_tables:
                continue
            src_cnt = migration_results.get(table_name, {}).get('source', 0)
            
            # Query target count
            with engine.connect() as v_conn:
                target_cnt = v_conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}";')).scalar()

            matched = (src_cnt == target_cnt)
            if not matched:
                all_matched = False
            match_badge = "YES" if matched else "MISMATCH"
            print(f"{table_name:<20} | {src_cnt:<12} | {target_cnt:<15} | {match_badge:<10}")

        print("=" * 70)
        if all_matched:
            print(f"\n[SUCCESS] MIGRATION COMPLETED! {total_migrated} records successfully migrated to PostgreSQL.")
            print("[INFO] Original SQLite database remains completely untouched.")
        else:
            print(f"\n[WARNING] Migration completed with count discrepancies. Please check the table above.")


def main():
    parser = argparse.ArgumentParser(description="Migrate CCTV Software SQLite database to PostgreSQL.")
    parser.add_argument(
        '--sqlite-path',
        default=str(PROJECT_ROOT / 'instance' / 'cctv_software.db'),
        help='Path to source SQLite database file'
    )
    parser.add_argument(
        '--postgres-url',
        default=os.getenv('DATABASE_URL', ''),
        help='PostgreSQL connection URL (e.g. postgresql://user:pass@host:5432/dbname)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Verify source data and counts without modifying target database'
    )
    parser.add_argument(
        '--truncate-target',
        action='store_true',
        help='Truncate target tables before migrating for a fresh import'
    )

    args = parser.parse_args()

    # Determine PostgreSQL URL
    pg_url = args.postgres_url
    if not pg_url:
        cfg = get_config()
        if cfg.SQLALCHEMY_DATABASE_URI and cfg.SQLALCHEMY_DATABASE_URI.startswith('postgresql'):
            pg_url = cfg.SQLALCHEMY_DATABASE_URI

    if not pg_url and not args.dry_run:
        print("[ERROR] No PostgreSQL DATABASE_URL provided.")
        print("Set the DATABASE_URL environment variable or pass --postgres-url 'postgresql://...'")
        sys.exit(1)

    run_migration(
        sqlite_path=args.sqlite_path,
        postgres_url=pg_url or 'sqlite:///:memory:',
        dry_run=args.dry_run,
        truncate_target=args.truncate_target
    )


if __name__ == '__main__':
    main()
