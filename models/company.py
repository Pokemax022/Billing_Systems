from database.db import db

class CompanySettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.Text)
    mobile = db.Column(db.String(50))
    email = db.Column(db.String(100))
    gstin = db.Column(db.String(50))
    
    bank_name = db.Column(db.String(100))
    account_number = db.Column(db.String(100))
    ifsc_code = db.Column(db.String(50))
    
    terms_conditions = db.Column(db.Text)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

