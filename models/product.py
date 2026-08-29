from database.db import db
from datetime import datetime

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    hsn_code = db.Column(db.String(50))
    brand = db.Column(db.String(100))
    warranty = db.Column(db.String(50))
    unit = db.Column(db.String(20), default='Pcs')
    dealer_price = db.Column(db.Float, default=0.0)
    customer_price = db.Column(db.Float, default=0.0)
    gst_percent = db.Column(db.Float, default=18.0)
    stock = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

