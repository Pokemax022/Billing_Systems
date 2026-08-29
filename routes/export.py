import io
import pandas as pd
from flask import Blueprint, send_file, flash, redirect, url_for
from flask_login import login_required
from models.customer import Customer
from models.product import Product
from models.quotation import Quotation

export_bp = Blueprint('export', __name__, url_prefix='/export')

@export_bp.route('/customers')
@login_required
def export_customers():
    customers = Customer.query.all()
    if not customers:
        flash('No customers to export.', 'warning')
        return redirect(url_for('customers.index'))
        
    data = []
    for c in customers:
        data.append({
            'Name': c.name,
            'Mobile': c.mobile,
            'Alternate Number': c.alternate_number,
            'Email': c.email,
            'Address': c.address,
            'Site Location': c.site_location,
            'City': c.city,
            'State': c.state,
            'PIN Code': c.pin_code,
            'Contact Person': c.contact_person,
            'GSTIN': c.gst_number,
            'Total Business Amount': c.total_business_amount
        })
        
    df = pd.DataFrame(data)
    
    # Create in-memory Excel file
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Customers')
        
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='Customers_Export.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@export_bp.route('/products')
@login_required
def export_products():
    products = Product.query.all()
    if not products:
        flash('No products to export.', 'warning')
        return redirect(url_for('products.index'))
        
    data = []
    for p in products:
        data.append({
            'Name': p.name,
            'HSN': p.hsn_code,
            'Brand': p.brand,
            'Warranty': p.warranty,
            'Unit': p.unit,
            'Dealer Price': p.dealer_price,
            'Customer Price': p.customer_price,
            'GST %': p.gst_percent,
            'Stock': p.stock,
            'Notes': p.notes
        })
        
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Products')
        
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='Products_Export.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@export_bp.route('/profit_report')
@login_required
def export_profit_report():
    quotations = Quotation.query.all()
    data = []
    for q in quotations:
        data.append({
            'Quotation Number': q.quotation_number,
            'Date': q.date.strftime('%Y-%m-%d') if q.date else 'N/A',
            'Customer': q.customer.name if q.customer else 'Deleted Customer',
            'Total Revenue': q.grand_total or 0.0,
            'Total Dealer Cost': q.total_dealer_cost or 0.0,
            'Net Profit': (q.grand_total or 0.0) - (q.total_dealer_cost or 0.0) - ((q.cgst_total or 0.0) + (q.sgst_total or 0.0) + (q.igst_total or 0.0)),
            'Status': q.status or 'Draft'
        })
        
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Profit Report')
        
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='Profit_Report.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
