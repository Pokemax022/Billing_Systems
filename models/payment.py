from database.db import db
from datetime import datetime, date

# Payment for Quotations (legacy — kept as-is).
# Invoice payments use InvoicePayment in models/invoice.py.
class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey('quotation.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, default=date.today)  # callable, evaluated fresh each insert
    payment_method = db.Column(db.String(50)) # Cash, Bank Transfer, UPI, Cheque
    reference_number = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

