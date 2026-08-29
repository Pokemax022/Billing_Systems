from database.db import db
from datetime import datetime

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    mobile = db.Column(db.String(20), nullable=True)
    alternate_number = db.Column(db.String(20))
    email = db.Column(db.String(150))
    address = db.Column(db.Text)
    site_location = db.Column(db.String(255))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    pin_code = db.Column(db.String(20))
    contact_person = db.Column(db.String(150))
    gst_number = db.Column(db.String(50))
    total_business_amount = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    quotations = db.relationship('Quotation', backref='customer', lazy=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

