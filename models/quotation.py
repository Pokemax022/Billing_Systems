from database.db import db
from datetime import datetime, date
from models.payment import Payment

class Quotation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quotation_number = db.Column(db.String(50), unique=True, nullable=False)
    date = db.Column(db.Date, default=date.today)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True)
    
    sub_total = db.Column(db.Float, default=0.0)
    cgst_total = db.Column(db.Float, default=0.0)
    sgst_total = db.Column(db.Float, default=0.0)
    igst_total = db.Column(db.Float, default=0.0)
    
    installation_qty = db.Column(db.Integer, default=1)
    installation_rate = db.Column(db.Float, default=0.0)   # per-unit price
    installation_charges = db.Column(db.Float, default=0.0) # total = rate × qty
    wiring_charges = db.Column(db.Float, default=0.0)
    transport_charges = db.Column(db.Float, default=0.0)
    
    grand_total = db.Column(db.Float, default=0.0)
    total_dealer_cost = db.Column(db.Float, default=0.0) # Hidden from customer
    
    notes = db.Column(db.Text)
    warranty_notes = db.Column(db.Text)
    
    status = db.Column(db.String(50), default='Draft') # Draft, Sent, Accepted, Invoiced
    payment_status = db.Column(db.String(50), default='Unpaid') # Unpaid, Partial, Paid
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # callable, evaluated fresh each insert
    items = db.relationship('QuotationItem', backref='quotation', cascade="all, delete-orphan", lazy=True)
    payments = db.relationship('Payment', backref='quotation', cascade="all, delete-orphan", lazy=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class QuotationItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotation.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)
    
    name = db.Column(db.String(255), nullable=False) # Store snapshot
    hsn_code = db.Column(db.String(50))
    quantity = db.Column(db.Integer, default=1)
    
    dealer_price = db.Column(db.Float, default=0.0) # Snapshot for historical profit
    selling_price = db.Column(db.Float, default=0.0) # Rate
    
    gst_percent = db.Column(db.Float, default=18.0)
    taxable_value = db.Column(db.Float, default=0.0) # Qty * Selling Price

    def __init__(self, **kwargs):
        super().__init__(**kwargs)



