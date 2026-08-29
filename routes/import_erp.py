import os
import re
import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_required
from models.customer import Customer
from models.product import Product
from models.quotation import Quotation, QuotationItem
from models.import_log import ImportLog
from database.db import db
from werkzeug.utils import secure_filename
from datetime import datetime

import_erp_bp = Blueprint('import_erp', __name__, url_prefix='/erp')

def strict_clean_value(val):
    if pd.isna(val) or str(val).strip().lower() == 'nan': return ''
    val = str(val).strip()
    # If the value contains ':-', take everything after it
    if ':-' in val:
        parts = val.split(':-', 1)
        val = parts[1].strip()
    # Further cleanup: remove any leading weird characters or extra spaces
    val = re.sub(r'^\s*[:\-]+\s*', '', val)
    return val

@import_erp_bp.route('/hub', methods=['GET', 'POST'])
@login_required
def hub():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file uploaded', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
            
        if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.csv')):
            filename = secure_filename(file.filename)
            upload_dir = current_app.config.get('UPLOAD_FOLDER', os.path.join(current_app.root_path, 'excel_import'))
            os.makedirs(upload_dir, exist_ok=True)
            filepath = os.path.join(upload_dir, filename)
            file.save(filepath)
            
            try:
                xl = pd.ExcelFile(filepath)
                sheets = xl.sheet_names
                session['import_file'] = filepath
                session['sheets'] = sheets
                return redirect(url_for('import_erp.select_sheet'))
            except Exception as e:
                flash(f'Error reading Excel file: {str(e)}', 'danger')
                
    return render_template('erp/hub.html')

@import_erp_bp.route('/select_sheet', methods=['GET', 'POST'])
@login_required
def select_sheet():
    if 'import_file' not in session: return redirect(url_for('import_erp.hub'))
    
    if request.method == 'POST':
        sheet = request.form.get('sheet')
        action = request.form.get('action')
        
        session['selected_sheet'] = sheet
        session['import_action'] = action
        
        if action == 'quotation':
            return redirect(url_for('import_erp.process_quotation'))
        else:
            return redirect(url_for('import_erp.preview', import_type=action))
            
    return render_template('erp/select_sheet.html', sheets=session.get('sheets', []))

@import_erp_bp.route('/preview/<import_type>', methods=['GET', 'POST'])
@login_required
def preview(import_type):
    if 'import_file' not in session: return redirect(url_for('import_erp.hub'))
    
    filepath = session['import_file']
    sheet = session['selected_sheet']
    
    # Read headerless because the data is visually unstructured
    df = pd.read_excel(filepath, sheet_name=sheet, header=None)
    
    cleaned_data = []
    
    if import_type == 'customers':
        # STRICT CUSTOMER PARSER (NAME sheet)
        # Col 0: Name, Col 1: Mobile, Col 2: GSTIN, Col 3: Address
        for _, row in df.iterrows():
            if len(row) < 1: continue
            raw_name_col = str(row[0]).strip()
            
            # Must look like a name row or contain 'Name :-'
            if not raw_name_col or raw_name_col.lower() == 'nan': continue
            # Only process if it explicitly has 'Name' or if the user forced it, we assume Col 0 is name
            if 'name' not in raw_name_col.lower() and len(raw_name_col) < 3:
                continue
                
            name = strict_clean_value(raw_name_col)
            if not name: continue # Skip if empty after clean
            
            mobile = strict_clean_value(row[1]) if len(row) > 1 else ''
            gst = strict_clean_value(row[2]) if len(row) > 2 else ''
            address = strict_clean_value(row[3]) if len(row) > 3 else ''
            
            # Clean mobile (extract just digits and plus)
            mobile = re.sub(r'[^\d\+]', '', mobile)
            
            cleaned_data.append({
                'name': name,
                'mobile': mobile,
                'gst_number': gst,
                'address': address
            })
            
    elif import_type == 'products':
        # STRICT PRODUCT PARSER (PRODUCT sheet)
        # Col 0: Product Name, Col 1: HSN
        for _, row in df.iterrows():
            if len(row) < 1: continue
            name = str(row[0]).strip()
            if not name or name.lower() == 'nan': continue
            
            # Skip rows that look like formatting or headers
            if name.lower() in ['product name', 'item name', 'particulars', 'sl no', 'sr no']:
                continue
                
            hsn = str(row[1]).strip() if len(row) > 1 else ''
            if hsn.lower() == 'nan': hsn = ''
            
            cleaned_data.append({
                'name': name,
                'hsn_code': hsn
            })

    if request.method == 'POST':
        success_count = 0
        duplicate_count = 0
        
        for data in cleaned_data:
            if import_type == 'customers':
                existing = None
                if data.get('mobile'):
                    existing = Customer.query.filter_by(mobile=data['mobile']).first()
                if not existing and data.get('name'):
                    existing = Customer.query.filter(Customer.name.ilike(data['name'])).first()
                    
                if existing:
                    for k, v in data.items():
                        if v and not getattr(existing, k, None): setattr(existing, k, v)
                    duplicate_count += 1
                else:
                    db.session.add(Customer(**data))
                    success_count += 1
                    
            elif import_type == 'products':
                existing = Product.query.filter(Product.name.ilike(data['name'])).first()
                if existing:
                    if data.get('hsn_code') and not existing.hsn_code: existing.hsn_code = data['hsn_code']
                    duplicate_count += 1
                else:
                    db.session.add(Product(**data))
                    success_count += 1
                    
        db.session.add(ImportLog(import_type=import_type, filename=os.path.basename(filepath), total_rows=len(df), imported_rows=success_count, duplicate_rows=duplicate_count))
        db.session.commit()
        
        flash(f'Strict Import Complete: {success_count} added, {duplicate_count} merged/skipped.', 'success')
        return redirect(url_for('products.index' if import_type == 'products' else 'customers.index'))
        
    return render_template('erp/preview.html', cleaned_data=cleaned_data, import_type=import_type)

@import_erp_bp.route('/process_quotation')
@login_required
def process_quotation():
    if 'import_file' not in session: return redirect(url_for('import_erp.hub'))
    
    filepath = session['import_file']
    sheet = session['selected_sheet']
    df = pd.read_excel(filepath, sheet_name=sheet, header=None)
    
    cust_name = ""
    cust_mobile = ""
    
    for _, row in df.iterrows():
        for val in row.values:
            val_str = str(val)
            if 'Name :-' in val_str:
                cust_name = strict_clean_value(val_str)
            if 'Mobile No.:-' in val_str or 'PH.:' in val_str:
                nums = re.findall(r'\d{10}', val_str)
                if nums: cust_mobile = nums[0]
                
    if not cust_name: cust_name = "Imported Customer " + datetime.now().strftime('%Y%m%d%H%M')
    
    customer = Customer.query.filter(Customer.name.ilike(cust_name.strip())).first()
    if not customer:
        customer = Customer(name=cust_name.strip(), mobile=cust_mobile or None)
        db.session.add(customer)
        db.session.commit()
        
    start_idx = -1
    for idx, row in df.iterrows():
        row_str = ' '.join([str(x) for x in row.values]).lower()
        if 'product' in row_str and 'rate' in row_str:
            start_idx = idx + 1
            break
            
    items = []
    if start_idx != -1:
        for idx in range(start_idx, len(df)):
            row = df.iloc[idx].values
            item_name = str(row[1]).strip() if len(row) > 1 else ''
            if not item_name or item_name.lower() == 'nan': continue
            if 'installation' in item_name.lower() or 'wireing' in item_name.lower(): continue
            
            try:
                hsn = str(row[2]).strip() if len(row) > 2 and not pd.isna(row[2]) else ''
                qty_raw = str(row[3]).strip() if len(row) > 3 else '1'
                qty = int(qty_raw) if qty_raw.isdigit() else 1
                rate_raw = str(row[4]).strip() if len(row) > 4 else '0'
                clean_rate = re.sub(r'[^\d\.]', '', rate_raw)
                rate = float(clean_rate) if clean_rate else 0.0
                items.append({'name': item_name, 'hsn': hsn, 'qty': qty, 'rate': rate})
            except Exception:
                pass
                
    # Generate unique candidate quotation number
    candidate_num = f"IMP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    counter = 1
    while Quotation.query.filter_by(quotation_number=candidate_num).first():
        candidate_num = f"IMP-{datetime.now().strftime('%Y%m%d%H%M%S')}-{counter}"
        counter += 1

    quote = Quotation(quotation_number=candidate_num, customer_id=customer.id)
    db.session.add(quote)
    db.session.flush()
    
    sub_total = 0
    total_dealer_cost = 0.0
    for itm in items:
        taxable = itm['qty'] * itm['rate']
        sub_total += taxable
        
        # Look up product to get dealer price snapshot
        p = Product.query.filter(Product.name.ilike(itm['name'])).first()
        dp_ex_gst = (p.dealer_price / (1 + p.gst_percent / 100)) if p else 0.0
        total_dealer_cost += dp_ex_gst * itm['qty']
        
        qi = QuotationItem(
            quotation_id=quote.id,
            product_id=p.id if p else None,
            name=itm['name'],
            hsn_code=itm['hsn'],
            quantity=itm['qty'],
            dealer_price=dp_ex_gst,
            selling_price=itm['rate'],
            taxable_value=taxable
        )
        db.session.add(qi)
        
    quote.sub_total = sub_total
    quote.total_dealer_cost = total_dealer_cost
    quote.cgst_total = sub_total * 0.09
    quote.sgst_total = sub_total * 0.09
    quote.grand_total = sub_total + quote.cgst_total + quote.sgst_total
    
    db.session.commit()
    
    flash('Quotation auto-generated successfully from Excel!', 'success')
    return redirect(url_for('quotations.view', id=quote.id))

@import_erp_bp.route('/logs')
@login_required
def logs():
    import_logs = ImportLog.query.order_by(ImportLog.created_at.desc()).all()
    return render_template('erp/logs.html', logs=import_logs)
