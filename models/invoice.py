from database.db import db
from datetime import datetime, date


class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    date = db.Column(db.Date, default=date.today)
    due_date = db.Column(db.Date, nullable=True)
    reference_number = db.Column(db.String(100))  # Quotation ref or PO number

    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True)

    # Discount
    discount_type = db.Column(db.String(20), default='percent')  # 'percent' or 'fixed'
    discount_value = db.Column(db.Float, default=0.0)            # e.g. 10 (%) or 500 (₹)
    discount_amount = db.Column(db.Float, default=0.0)           # computed absolute discount

    # Totals
    sub_total = db.Column(db.Float, default=0.0)          # sum of taxable values (qty × rate)
    cgst_total = db.Column(db.Float, default=0.0)
    sgst_total = db.Column(db.Float, default=0.0)
    igst_total = db.Column(db.Float, default=0.0)

    # Additional charges (same as quotation)
    installation_qty = db.Column(db.Integer, default=1)
    installation_rate = db.Column(db.Float, default=0.0)
    installation_charges = db.Column(db.Float, default=0.0)
    wiring_charges = db.Column(db.Float, default=0.0)
    transport_charges = db.Column(db.Float, default=0.0)

    grand_total = db.Column(db.Float, default=0.0)

    # Payment tracking
    paid_amount = db.Column(db.Float, default=0.0)
    balance_due = db.Column(db.Float, default=0.0)

    # Status
    payment_status = db.Column(db.String(30), default='Pending')
    # Pending | Paid | Partially Paid | Overdue | Cancelled

    payment_method = db.Column(db.String(50))  # Cash, Bank Transfer, UPI, Cheque

    # Notes
    notes = db.Column(db.Text)
    terms_conditions = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer = db.relationship('Customer', backref=db.backref('invoices', lazy=True), lazy=True, foreign_keys=[customer_id])
    items = db.relationship('InvoiceItem', backref='invoice',
                            cascade='all, delete-orphan', lazy=True)
    payments = db.relationship('InvoicePayment', backref='invoice',
                               cascade='all, delete-orphan', lazy=True)

    @property
    def total_tax(self):
        return self.cgst_total + self.sgst_total + self.igst_total

    @property
    def is_overdue(self):
        if self.due_date and self.payment_status not in ('Paid', 'Cancelled'):
            return date.today() > self.due_date
        return False

    def recalculate_balance(self):
        """Recalculate paid_amount and balance_due from InvoicePayments."""
        self.paid_amount = sum(p.amount for p in self.payments)
        self.balance_due = max(0.0, round(self.grand_total - self.paid_amount, 2))
        if self.paid_amount <= 0:
            if self.is_overdue:
                self.payment_status = 'Overdue'
            else:
                self.payment_status = 'Pending'
        elif self.balance_due <= 0:
            self.payment_status = 'Paid'
        else:
            self.payment_status = 'Partially Paid'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True)

    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    hsn_code = db.Column(db.String(50))

    quantity = db.Column(db.Float, default=1.0)
    unit_price = db.Column(db.Float, default=0.0)   # Rate ex-GST

    discount_percent = db.Column(db.Float, default=0.0)
    gst_percent = db.Column(db.Float, default=18.0)

    taxable_value = db.Column(db.Float, default=0.0)  # qty × rate − line discount
    tax_amount = db.Column(db.Float, default=0.0)
    line_total = db.Column(db.Float, default=0.0)     # taxable + tax

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class InvoicePayment(db.Model):
    """Individual payment entries recorded against an invoice."""
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, default=date.today)
    payment_method = db.Column(db.String(50))  # Cash, Bank Transfer, UPI, Cheque
    reference_number = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

