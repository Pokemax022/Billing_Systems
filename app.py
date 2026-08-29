import os
import logging
from flask import Flask, render_template, jsonify, request
from database.db import db
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash
from config import get_config, Config
import models

# Initialize Flask-Migrate instance
migrate = Migrate()
csrf = CSRFProtect()
login_manager = LoginManager()


def create_app(config_object=None):
    """Application Factory for CCTV Software."""
    app = Flask(__name__)
    
    # Load configuration
    if config_object is None:
        config_object = get_config()
    app.config.from_object(config_object)

    # Ensure required directories exist
    os.makedirs(app.config.get('UPLOAD_FOLDER', os.path.join(app.root_path, 'excel_import')), exist_ok=True)
    os.makedirs(app.config.get('PDF_FOLDER', os.path.join(app.root_path, 'pdf')), exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        from models.user import User
        return db.session.get(User, int(user_id))

    # Register Blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.customers import customers_bp
    from routes.products import products_bp
    from routes.quotations import quotations_bp
    from routes.import_erp import import_erp_bp
    from routes.export import export_bp
    from routes.invoices import invoices_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(quotations_bp)
    app.register_blueprint(import_erp_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(invoices_bp)

    # Register Error Handlers
    register_error_handlers(app)

    # Register CLI Commands
    register_commands(app)

    return app


def register_error_handlers(app):
    """Register custom error handlers that do not leak sensitive information."""
    
    @app.errorhandler(400)
    def bad_request(error):
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({'error': 'Bad Request', 'message': str(error)}), 400
        return render_template('errors/400.html', error_message=str(error)), 400

    @app.errorhandler(403)
    def forbidden(error):
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({'error': 'Forbidden', 'message': 'Access denied'}), 403
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({'error': 'Not Found', 'message': 'Resource not found'}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        logging.exception("Internal Server Error: %s", error)
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({'error': 'Internal Server Error', 'message': 'An unexpected server error occurred'}), 500
        return render_template('errors/500.html'), 500


def register_commands(app):
    """Register custom Flask CLI management commands."""
    
    @app.cli.command('init-db')
    def init_db_command():
        """Initialize database tables and create default admin and company settings."""
        db.create_all()
        from models.user import User
        from models.company import CompanySettings

        admin_created = False
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password=generate_password_hash('admin123'))
            db.session.add(admin)
            admin_created = True

        settings_created = False
        if not CompanySettings.query.first():
            settings = CompanySettings(
                name='MISTHI ENTERPRISE',
                address='409, Wing B, Megh Palace, Godha Street, Nanpura, Surat - 395001',
                mobile='+91 87803 33801',
                email='rvandana616@gmail.com',
                gstin='24CGGPR3272P3ZR',
                bank_name='Bank of Baroda',
                account_number='21850200003826',
                ifsc_code='BARB0NANPUR',
                terms_conditions='1. Goods once sold will not be taken back.\n2. Warranty as per OEM.'
            )
            db.session.add(settings)
            settings_created = True

        db.session.commit()
        print("[OK] Database initialized successfully.")
        if admin_created:
            print("     Created default admin user (username: admin).")
        if settings_created:
            print("     Created default company settings.")


# Global WSGI application instance for Gunicorn / Render / Railway / PythonAnywhere
app = create_app()


if __name__ == '__main__':
    # When run directly in development, ensure database is initialized
    with app.app_context():
        db.create_all()
        from models.user import User
        from models.company import CompanySettings

        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password=generate_password_hash('admin123'))
            db.session.add(admin)
            db.session.commit()

        if not CompanySettings.query.first():
            settings = CompanySettings(
                name='MISTHI ENTERPRISE',
                address='409, Wing B, Megh Palace, Godha Street, Nanpura, Surat - 395001',
                mobile='+91 87803 33801',
                email='rvandana616@gmail.com',
                gstin='24CGGPR3272P3ZR',
                bank_name='Bank of Baroda',
                account_number='21850200003826',
                ifsc_code='BARB0NANPUR',
                terms_conditions='1. Goods once sold will not be taken back.\n2. Warranty as per OEM.'
            )
            db.session.add(settings)
            db.session.commit()

    port = int(os.getenv('PORT', 5001))
    app.run(debug=True, port=port)
