from database.db import db
from datetime import datetime

class ImportLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    import_type = db.Column(db.String(50)) # 'customer' or 'product'
    filename = db.Column(db.String(255))
    total_rows = db.Column(db.Integer, default=0)
    imported_rows = db.Column(db.Integer, default=0)
    failed_rows = db.Column(db.Integer, default=0)
    duplicate_rows = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default='Completed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

