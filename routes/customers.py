from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models.customer import Customer
from database.db import db

customers_bp = Blueprint('customers', __name__, url_prefix='/customers')

@customers_bp.route('/')
@login_required
def index():
    customers = Customer.query.order_by(Customer.created_at.desc()).all()
    return render_template('customers/index.html', customers=customers)

@customers_bp.route('/add', methods=['GET', 'POST'])
@customers_bp.route('/create', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        mobile = request.form.get('mobile', '').strip()
        email = request.form.get('email', '').strip()
        address = request.form.get('address', '').strip()
        site_location = request.form.get('site_location', '').strip()
        gst_number = request.form.get('gst_number', '').strip()
        alternate_number = request.form.get('alternate_number', '').strip()
        contact_person = request.form.get('contact_person', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        pin_code = request.form.get('pin_code', '').strip()
        
        customer = Customer(name=name, mobile=mobile, email=email, address=address, 
                            site_location=site_location, gst_number=gst_number,
                            alternate_number=alternate_number, contact_person=contact_person,
                            city=city, state=state, pin_code=pin_code)
        db.session.add(customer)
        db.session.commit()
        flash('Customer added successfully', 'success')
        return redirect(url_for('customers.index'))
        
    return render_template('customers/add.html')

@customers_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    customer = db.get_or_404(Customer, id)
    if request.method == 'POST':
        customer.name = request.form.get('name', '').strip()
        customer.mobile = request.form.get('mobile', '').strip()
        customer.email = request.form.get('email', '').strip()
        customer.address = request.form.get('address', '').strip()
        customer.site_location = request.form.get('site_location', '').strip()
        customer.gst_number = request.form.get('gst_number', '').strip()
        customer.alternate_number = request.form.get('alternate_number', '').strip()
        customer.contact_person = request.form.get('contact_person', '').strip()
        customer.city = request.form.get('city', '').strip()
        customer.state = request.form.get('state', '').strip()
        customer.pin_code = request.form.get('pin_code', '').strip()
        
        db.session.commit()
        flash('Customer updated successfully', 'success')
        return redirect(url_for('customers.index'))
        
    return render_template('customers/edit.html', customer=customer)

@customers_bp.route('/api/get/<int:id>')
@login_required
def api_get_customer(id):
    from flask import jsonify
    c = db.get_or_404(Customer, id)
    return jsonify({
        'id': c.id,
        'name': c.name,
        'mobile': c.mobile or '',
        'alternate_number': c.alternate_number or '',
        'email': c.email or '',
        'address': c.address or '',
        'site_location': c.site_location or '',
        'city': c.city or '',
        'state': c.state or '',
        'pin_code': c.pin_code or '',
        'contact_person': c.contact_person or '',
        'gst_number': c.gst_number or ''
    })

@customers_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    customer = db.get_or_404(Customer, id)
    db.session.delete(customer)
    db.session.commit()
    flash('Customer deleted successfully', 'success')
    return redirect(url_for('customers.index'))
