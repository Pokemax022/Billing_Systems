import os
import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required
from models.product import Product
from database.db import db
from werkzeug.utils import secure_filename

products_bp = Blueprint('products', __name__, url_prefix='/products')

@products_bp.route('/')
@login_required
def index():
    products = Product.query.order_by(Product.created_at.desc()).all()
    total_products = len(products)
    valid_prices = [p.customer_price for p in products if p.customer_price is not None and p.customer_price > 0]
    avg_customer_price = (sum(valid_prices) / len(valid_prices)) if valid_prices else 0.0
    total_stock = sum((p.stock or 0) for p in products)
    return render_template(
        'products/index.html',
        products=products,
        total_products=total_products,
        avg_customer_price=avg_customer_price,
        total_stock=total_stock
    )

def _safe_float(val, default=0.0):
    if val is None or val == '':
        return default
    try:
        import re
        clean = re.sub(r'[^\d\.-]', '', str(val))
        return float(clean) if clean else default
    except (ValueError, TypeError):
        return default

def _safe_int(val, default=0):
    if val is None or val == '':
        return default
    try:
        import re
        clean = re.sub(r'[^\d-]', '', str(val))
        return int(float(clean)) if clean else default
    except (ValueError, TypeError):
        return default

@products_bp.route('/add', methods=['GET', 'POST'])
@products_bp.route('/create', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        product = Product(
            name=request.form.get('name', '').strip(),
            hsn_code=request.form.get('hsn_code', '').strip(),
            brand=request.form.get('brand', '').strip(),
            warranty=request.form.get('warranty', '').strip(),
            unit=request.form.get('unit', 'Pcs').strip() or 'Pcs',
            dealer_price=_safe_float(request.form.get('dealer_price'), 0.0),
            customer_price=_safe_float(request.form.get('customer_price'), 0.0),
            gst_percent=_safe_float(request.form.get('gst_percent'), 18.0),
            stock=_safe_int(request.form.get('stock'), 0),
            notes=request.form.get('notes', '').strip()
        )
        db.session.add(product)
        db.session.commit()
        flash('Product added successfully', 'success')
        return redirect(url_for('products.index'))
        
    return render_template('products/add.html')

@products_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    product = db.get_or_404(Product, id)
    if request.method == 'POST':
        product.name = request.form.get('name', '').strip()
        product.hsn_code = request.form.get('hsn_code', '').strip()
        product.brand = request.form.get('brand', '').strip()
        product.warranty = request.form.get('warranty', '').strip()
        product.unit = request.form.get('unit', 'Pcs').strip() or 'Pcs'
        product.dealer_price = _safe_float(request.form.get('dealer_price'), 0.0)
        product.customer_price = _safe_float(request.form.get('customer_price'), 0.0)
        product.gst_percent = _safe_float(request.form.get('gst_percent'), 18.0)
        product.stock = _safe_int(request.form.get('stock'), 0)
        product.notes = request.form.get('notes', '').strip()
        
        db.session.commit()
        flash('Product updated successfully', 'success')
        return redirect(url_for('products.index'))
        
    return render_template('products/edit.html', product=product)

@products_bp.route('/import', methods=['GET', 'POST'])
@login_required
def import_excel():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
            
        if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.csv')):
            filename = secure_filename(file.filename)
            upload_dir = current_app.config.get('UPLOAD_FOLDER', os.path.join(current_app.root_path, 'excel_import'))
            os.makedirs(upload_dir, exist_ok=True)
            filepath = os.path.join(upload_dir, filename)
            file.save(filepath)
            
            try:
                if filename.endswith('.csv'):
                    df = pd.read_csv(filepath)
                else:
                    df = pd.read_excel(filepath)
                
                # Expected columns: Name, HSN, Brand, Warranty, Unit, Dealer Price, Customer Price, GST, Stock
                for _, row in df.iterrows():
                    # Simple mapping logic
                    name = str(row.get('Name', '')).strip()
                    if not name or name.lower() == 'nan':
                        continue
                        
                    product = Product.query.filter(Product.name.ilike(name)).first()
                    if not product:
                        product = Product(name=name)
                        db.session.add(product)
                        
                    product.hsn_code = str(row.get('HSN', '') if not pd.isna(row.get('HSN')) else '').strip()
                    product.brand = str(row.get('Brand', '') if not pd.isna(row.get('Brand')) else '').strip()
                    product.warranty = str(row.get('Warranty', '') if not pd.isna(row.get('Warranty')) else '').strip()
                    product.unit = str(row.get('Unit', 'Pcs') if not pd.isna(row.get('Unit')) else 'Pcs').strip() or 'Pcs'
                    product.dealer_price = _safe_float(row.get('Dealer Price'), 0.0)
                    product.customer_price = _safe_float(row.get('Customer Price'), 0.0)
                    product.gst_percent = _safe_float(row.get('GST'), 18.0)
                    product.stock = _safe_int(row.get('Stock'), 0)
                
                db.session.commit()
                flash('Products imported successfully', 'success')
                
            except Exception as e:
                flash(f'Error importing file: {str(e)}', 'danger')
            finally:
                if os.path.exists(filepath):
                    os.remove(filepath)
            
            return redirect(url_for('products.index'))
            
    return render_template('products/import.html')

@products_bp.route('/api/search')
@login_required
def api_search():
    q = request.args.get('q', '')
    if not q:
        products = Product.query.limit(50).all()
    else:
        products = Product.query.filter(Product.name.ilike(f'%{q}%')).limit(50).all()
    return jsonify({
        'results': [
            {
                'id': p.id,
                'text': p.name or 'Unnamed Product',
                'price': round((p.customer_price or 0.0) / (1 + (p.gst_percent if p.gst_percent is not None else 18.0) / 100), 2) if p.customer_price else 0.0,
                'gst': p.gst_percent if p.gst_percent is not None else 18.0,
                'hsn': p.hsn_code or '',
                'dealer_price': round((p.dealer_price or 0.0) / (1 + (p.gst_percent if p.gst_percent is not None else 18.0) / 100), 2) if p.dealer_price else 0.0
            } for p in products
        ]
    })

@products_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    product = db.get_or_404(Product, id)
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted successfully', 'success')
    return redirect(url_for('products.index'))
