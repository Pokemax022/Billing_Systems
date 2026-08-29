import logging
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required
from models.user import User
from werkzeug.security import check_password_hash

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash('Please enter both username and password.', 'warning')
            return render_template('login.html'), 400
            
        try:
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                login_user(user)
                next_page = request.args.get('next')
                # Validate next_page to prevent open redirect
                if next_page and next_page.startswith('/') and not next_page.startswith('//'):
                    return redirect(next_page)
                return redirect(url_for('dashboard.index'))
                
            flash('Invalid username or password', 'danger')
        except Exception as e:
            current_app.logger.exception("Database error during login for user '%s': %s", username, e)
            flash('A database connection error occurred. Please check your network or credentials and try again.', 'danger')
            return render_template('login.html'), 500
            
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
