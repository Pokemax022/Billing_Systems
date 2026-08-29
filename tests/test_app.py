import os
import sys
import unittest
from pathlib import Path
from datetime import date

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from werkzeug.security import generate_password_hash
from app import create_app
from database.db import db
from config import TestingConfig, normalize_database_url
from models.user import User
from models.customer import Customer
from models.product import Product
from models.quotation import Quotation, QuotationItem
from models.invoice import Invoice, InvoiceItem, InvoicePayment
from models.company import CompanySettings


class CCTVAppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        db.create_all()
        
        # Create test user
        self.user = User(username='testadmin', password=generate_password_hash('testpass123'))
        db.session.add(self.user)
        
        # Create test company settings
        self.company = CompanySettings(
            name='TEST CCTV SYSTEMS',
            address='101 Security Plaza, Tech Hub',
            mobile='+91 98765 43210',
            email='test@cctvsystems.com',
            gstin='24AABCU9603R1ZM'
        )
        db.session.add(self.company)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login(self, username='testadmin', password='testpass123'):
        return self.client.post('/login', data={
            'username': username,
            'password': password
        }, follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    # ──────────────────────────────────────────
    # 1. Configuration & URL Normalization
    # ──────────────────────────────────────────
    def test_database_url_normalization(self):
        legacy_url = "postgres://user:pass@ep-cool-fog.render.com:5432/mydb"
        normalized = normalize_database_url(legacy_url)
        self.assertTrue(normalized.startswith("postgresql://"))
        self.assertEqual(normalized, "postgresql://user:pass@ep-cool-fog.render.com:5432/mydb")

        standard_url = "postgresql://user:pass@localhost:5432/mydb"
        self.assertEqual(normalize_database_url(standard_url), standard_url)

    # ──────────────────────────────────────────
    # 2. Authentication
    # ──────────────────────────────────────────
    def test_login_logout(self):
        # Failed login
        res = self.login('testadmin', 'wrongpass')
        self.assertIn(b'Invalid username or password', res.data)

        # Successful login
        res = self.login('testadmin', 'testpass123')
        self.assertEqual(res.status_code, 200)

        # Logout
        res = self.logout()
        self.assertIn(b'Sign in to access your dashboard', res.data)

    def test_protected_routes_require_login(self):
        res = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res.headers.get('Location', ''))

    # ──────────────────────────────────────────
    # 3. Customer Operations
    # ──────────────────────────────────────────
    def test_customer_crud(self):
        self.login()
        
        # Create Customer
        res = self.client.post('/customers/add', data={
            'name': 'Acme Enterprise',
            'mobile': '9876500001',
            'email': 'contact@acme.com',
            'address': 'Industrial Area, Ring Road',
            'gst_number': '24AAACT1234F1Z0'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Customer added successfully', res.data)
        
        cust = Customer.query.filter_by(name='Acme Enterprise').first()
        self.assertIsNotNone(cust)
        self.assertEqual(cust.mobile, '9876500001')

        # Customer API
        api_res = self.client.get(f'/customers/api/get/{cust.id}')
        self.assertEqual(api_res.status_code, 200)
        data = api_res.get_json()
        self.assertEqual(data['name'], 'Acme Enterprise')

        # Edit Customer
        res = self.client.post(f'/customers/edit/{cust.id}', data={
            'name': 'Acme Enterprise Ltd',
            'mobile': '9876500002',
            'email': 'info@acme.com',
            'address': 'New Address',
            'gst_number': '24AAACT1234F1Z0'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        cust_updated = db.session.get(Customer, cust.id)
        self.assertEqual(cust_updated.name, 'Acme Enterprise Ltd')

        # Delete Customer
        res = self.client.post(f'/customers/delete/{cust.id}', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(db.session.get(Customer, cust.id))

    # ──────────────────────────────────────────
    # 4. Product Operations & Search API (None check)
    # ──────────────────────────────────────────
    def test_product_crud_and_search(self):
        self.login()
        
        # Add Product
        res = self.client.post('/products/add', data={
            'name': '4K Dome Camera Pro',
            'hsn_code': '85258000',
            'brand': 'CP Plus',
            'warranty': '2 Years',
            'unit': 'Pcs',
            'dealer_price': '2500',
            'customer_price': '3500',
            'gst_percent': '18',
            'stock': '15'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Product added successfully', res.data)

        prod = Product.query.filter_by(name='4K Dome Camera Pro').first()
        self.assertIsNotNone(prod)
        self.assertEqual(prod.stock, 15)

        # Test Search API (Validates is not None fix)
        search_res = self.client.get('/products/api/search?q=Dome')
        self.assertEqual(search_res.status_code, 200)
        results = search_res.get_json().get('results', [])
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]['text'], '4K Dome Camera Pro')

    # ──────────────────────────────────────────
    # 5. Quotation Operations
    # ──────────────────────────────────────────
    def test_quotation_creation_and_view(self):
        self.login()
        
        # Create customer & product
        cust = Customer(name='Hotel Blue Star', mobile='9898012345')
        prod = Product(name='8CH NVR', dealer_price=6000.0, customer_price=8500.0, gst_percent=18.0)
        db.session.add_all([cust, prod])
        db.session.commit()

        res = self.client.post('/quotations/create', data={
            'customer_id': str(cust.id),
            'installation_charges': '300',
            'installation_qty': '4',
            'wiring_charges': '500',
            'transport_charges': '200',
            'notes': 'Quotation for 8CH NVR system',
            'product_id[]': [str(prod.id)],
            'product_name[]': [prod.name],
            'quantity[]': ['2'],
            'selling_price[]': ['7500'],
            'gst_percent[]': ['18']
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        quote = Quotation.query.first()
        self.assertIsNotNone(quote)
        self.assertEqual(quote.sub_total, 15000.0)  # 2 * 7500
        self.assertEqual(quote.installation_charges, 1200.0)  # 300 * 4
        # Tax = 15000 * 18% = 2700 (CGST 1350 + SGST 1350)
        self.assertEqual(quote.cgst_total, 1350.0)
        self.assertEqual(quote.sgst_total, 1350.0)
        # Grand total = 15000 + 2700 + 1200 + 500 + 200 = 19600.0
        self.assertEqual(quote.grand_total, 19600.0)

        # View Quotation HTML Preview
        prev_res = self.client.get(f'/quotations/preview/{quote.id}?template=classic')
        self.assertEqual(prev_res.status_code, 200)
        self.assertIn(b'Hotel Blue Star', prev_res.data)

        # WhatsApp Menu
        wa_res = self.client.get(f'/quotations/whatsapp/{quote.id}')
        self.assertEqual(wa_res.status_code, 200)

    # ──────────────────────────────────────────
    # 6. Invoice & Payment Operations
    # ──────────────────────────────────────────
    def test_invoice_and_payment_flow(self):
        self.login()
        
        cust = Customer(name='Green Villa Society', mobile='9123456780')
        db.session.add(cust)
        db.session.commit()

        # Create Invoice
        res = self.client.post('/invoices/create', data={
            'customer_id': str(cust.id),
            'date': date.today().strftime('%Y-%m-%d'),
            'installation_charges': '250',
            'installation_qty': '2',
            'item_name[]': ['Outdoor Bullet Cam'],
            'item_desc[]': ['5MP IR Bullet Camera'],
            'item_hsn[]': ['85258000'],
            'item_qty[]': ['2'],
            'item_rate[]': ['3000'],
            'item_discount[]': ['0'],
            'item_gst[]': ['18']
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        inv = Invoice.query.first()
        self.assertIsNotNone(inv)
        # Taxable = 6000, Tax = 1080, Installation = 500 => Total = 7580.0
        self.assertEqual(inv.grand_total, 7580.0)
        self.assertEqual(inv.balance_due, 7580.0)
        self.assertEqual(inv.payment_status, 'Pending')

        # Record partial payment
        pay_res = self.client.post(f'/invoices/payment/{inv.id}', data={
            'amount': '3000',
            'payment_date': date.today().strftime('%Y-%m-%d'),
            'payment_method': 'UPI',
            'reference_number': 'UPI-REF-9988'
        }, follow_redirects=True)
        self.assertEqual(pay_res.status_code, 200)

        inv_updated = db.session.get(Invoice, inv.id)
        self.assertEqual(inv_updated.paid_amount, 3000.0)
        self.assertEqual(inv_updated.balance_due, 4580.0)
        self.assertEqual(inv_updated.payment_status, 'Partially Paid')

    # ──────────────────────────────────────────
    # 7. Dashboard & Analytics API
    # ──────────────────────────────────────────
    def test_dashboard_and_export(self):
        self.login()
        
        # Seed test customer and product for export testing
        cust = Customer(name='Export Test Customer', mobile='9876543210')
        prod = Product(name='Export Test Camera', dealer_price=1000.0, customer_price=1500.0)
        db.session.add_all([cust, prod])
        db.session.commit()

        # Dashboard index
        dash_res = self.client.get('/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn(b'Dashboard', dash_res.data)

        # Excel Exports
        res_cust = self.client.get('/export/customers')
        self.assertEqual(res_cust.status_code, 200)
        self.assertEqual(res_cust.headers['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        res_prod = self.client.get('/export/products')
        self.assertEqual(res_prod.status_code, 200)

        res_rep = self.client.get('/export/profit_report')
        self.assertEqual(res_rep.status_code, 200)

    # ──────────────────────────────────────────
    # 8. Error Handlers & APIs
    # ──────────────────────────────────────────
    def test_404_error_page(self):
        self.login()
        res = self.client.get('/non-existent-page-12345')
        self.assertEqual(res.status_code, 404)
        self.assertIn(b'Page Not Found', res.data)

    def test_quotation_profit_api(self):
        self.login()
        cust = Customer(name='Profit Test Customer')
        prod = Product(name='High Margin Camera', dealer_price=2000.0, customer_price=4000.0, gst_percent=18.0)
        db.session.add_all([cust, prod])
        db.session.commit()

        quote = Quotation(
            quotation_number='Q-TEST-PROFIT',
            customer_id=cust.id,
            sub_total=4000.0,
            grand_total=4720.0,
            total_dealer_cost=2000.0
        )
        db.session.add(quote)
        db.session.flush()

        qi = QuotationItem(
            quotation_id=quote.id,
            product_id=prod.id,
            name=prod.name,
            quantity=1,
            dealer_price=2000.0,
            selling_price=4000.0,
            taxable_value=4000.0
        )
        db.session.add(qi)
        db.session.commit()

        api_res = self.client.get(f'/api/quotation-profit/{quote.id}')
        self.assertEqual(api_res.status_code, 200)
        data = api_res.get_json()
        self.assertEqual(data['quotation_number'], 'Q-TEST-PROFIT')
        self.assertEqual(data['gross_profit'], 2000.0)

    def test_invoice_duplicate_and_delete(self):
        self.login()
        cust = Customer(name='Duplicate Inv Cust')
        db.session.add(cust)
        db.session.commit()

        inv = Invoice(
            invoice_number='INV-ORIG-001',
            customer_id=cust.id,
            sub_total=5000.0,
            grand_total=5900.0,
            balance_due=5900.0
        )
        db.session.add(inv)
        db.session.flush()

        item = InvoiceItem(
            invoice_id=inv.id,
            name='Test Item',
            quantity=1.0,
            unit_price=5000.0,
            taxable_value=5000.0,
            tax_amount=900.0,
            line_total=5900.0
        )
        db.session.add(item)
        db.session.commit()

        # Duplicate
        dup_res = self.client.post(f'/invoices/duplicate/{inv.id}', follow_redirects=False)
        self.assertEqual(dup_res.status_code, 302)
        all_invs = Invoice.query.all()
        self.assertEqual(len(all_invs), 2)

        # Delete
        del_res = self.client.post(f'/invoices/delete/{inv.id}', follow_redirects=True)
        self.assertEqual(del_res.status_code, 200)
        self.assertIsNone(db.session.get(Invoice, inv.id))

    def test_migration_row_sanitization(self):
        from scripts.migrate_sqlite_to_postgres import sanitize_row, parse_datetime, parse_date
        
        # Test Date parsing
        d = parse_date('2026-08-15')
        self.assertEqual(d, date(2026, 8, 15))

        # Test Datetime parsing
        dt = parse_datetime('2026-08-15 14:30:45.123456')
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.minute, 30)

        # Test Row Sanitization
        raw_row = {
            'id': '42',
            'grand_total': '12500.50',
            'date': '2026-08-10',
            'created_at': '2026-08-10 10:00:00',
            'notes': 'Test notes',
            'customer_id': '10'
        }
        sanitized = sanitize_row('quotation', raw_row)
        self.assertEqual(sanitized['id'], 42)
        self.assertEqual(sanitized['grand_total'], 12500.50)
        self.assertEqual(sanitized['customer_id'], 10)
        self.assertEqual(sanitized['date'], date(2026, 8, 10))


if __name__ == '__main__':
    unittest.main()
