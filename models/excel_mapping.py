from database.db import db
from datetime import datetime

class ExcelMapping(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mapping_type = db.Column(db.String(50)) # 'customer' or 'product'
    excel_column_name = db.Column(db.String(100), nullable=False)
    db_field_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

