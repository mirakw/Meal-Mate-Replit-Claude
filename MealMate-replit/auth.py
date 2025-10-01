"""
Independent Authentication System for MealMate
Provides user registration, login, and account management functionality.
"""

import os
import uuid
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Blueprint, request, redirect, url_for, flash, render_template, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
import logging

# Create auth blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


# Import models directly
from database import db
from models import User, PasswordResetToken


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration endpoint"""
    if request.method == 'GET':
        return render_template('auth/register.html')

    # Handle POST - registration logic
    # Get form data
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()

    # Validation
    errors = []

    if not email:
        errors.append('Email is required')
    elif '@' not in email or '.' not in email:
        errors.append('Please enter a valid email address')

    if not password:
        errors.append('Password is required')
    elif len(password) < 6:
        errors.append('Password must be at least 6 characters long')

    if password != confirm_password:
        errors.append('Passwords do not match')

    if not first_name:
        errors.append('First name is required')

    # Check if user already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        errors.append('An account with this email already exists')

    if errors:
        for error in errors:
            flash(error, 'error')
        return render_template('auth/register.html',
                               email=email,
                               first_name=first_name,
                               last_name=last_name)

    try:
        # Create new user
        user = User()
        user.id = str(uuid.uuid4())
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.set_password(password)
        user.email_verified = True  # Auto-verify for now
        user.oauth_provider = None  # This is a password-based account

        db.session.add(user)
        db.session.commit()

        # Create user directory structure
        user_dir = f"user_data/{user.id}"
        os.makedirs(user_dir, exist_ok=True)
        os.makedirs(f"{user_dir}/saved_recipes", exist_ok=True)

        # Create default folder structure
        from folder_manager import FolderManager
        user_folder_manager = FolderManager(
            folders_file=f"user_data/{user.id}/folders.json",
            recipes_dir=f"user_data/{user.id}/saved_recipes")
        user_folder_manager.create_folder("Uncategorized")

        # Log the user in
        login_user(user)

        flash('Account created successfully! Welcome to MealMate!', 'success')
        logging.info(f"New user registered: {email}")

        return redirect(url_for('index'))

    except Exception as e:
        db.session.rollback()
        logging.error(f"Registration error: {e}")
        flash(
            'An error occurred while creating your account. Please try again.',
            'error')
        return render_template('auth/register.html',
                               email=email,
                               first_name=first_name,
                               last_name=last_name)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login endpoint"""
    # If already signed in, go home
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    
    if request.method == 'GET':
        return render_template('auth/login.html')

    # Models are already imported at module level

    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    remember = request.form.get('remember') == 'on'

    # Validation
    if not email or not password:
        flash('Please enter both email and password', 'error')
        return render_template('auth/login.html', email=email)

    # Find user
    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        flash('Invalid email or password', 'error')
        return render_template('auth/login.html', email=email)

    # Log the user in
    login_user(user, remember=remember)

    # Create user directory if it doesn't exist (for legacy users)
    user_dir = f"user_data/{user.id}"
    os.makedirs(user_dir, exist_ok=True)
    os.makedirs(f"{user_dir}/saved_recipes", exist_ok=True)

    flash(f'Welcome back, {user.first_name}!', 'success')
    logging.info(f"User logged in: {email}")

    # Redirect to next page or home
    next_page = request.args.get('next')
    if next_page:
        return redirect(next_page)
    return redirect(url_for('index'))


@auth_bp.route('/logout')
@login_required
def logout():
    """User logout endpoint"""
    logout_user()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('index'))


@auth_bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    return render_template('auth/profile.html')


@auth_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    """Update user profile"""
    # Models are already imported at module level

    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()

    if not first_name:
        flash('First name is required', 'error')
        return redirect(url_for('auth.profile'))

    try:
        current_user.first_name = first_name
        current_user.last_name = last_name
        db.session.commit()

        flash('Profile updated successfully!', 'success')

    except Exception as e:
        db.session.rollback()
        logging.error(f"Profile update error: {e}")
        flash('An error occurred while updating your profile', 'error')

    return redirect(url_for('auth.profile'))


@auth_bp.route('/change_password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    # Models are already imported at module level

    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    # Validation
    if not current_user.check_password(current_password):
        flash('Current password is incorrect', 'error')
        return redirect(url_for('auth.profile'))

    if len(new_password) < 6:
        flash('New password must be at least 6 characters long', 'error')
        return redirect(url_for('auth.profile'))

    if new_password != confirm_password:
        flash('New passwords do not match', 'error')
        return redirect(url_for('auth.profile'))

    try:
        current_user.set_password(new_password)
        db.session.commit()

        flash('Password changed successfully!', 'success')
        logging.info(f"Password changed for user: {current_user.email}")

    except Exception as e:
        db.session.rollback()
        logging.error(f"Password change error: {e}")
        flash('An error occurred while changing your password', 'error')

    return redirect(url_for('auth.profile'))


@auth_bp.route('/demo_login')
def demo_login():
    """Create or login demo user for testing"""
    # Models are already imported at module level

    try:
        demo_user = User.query.filter_by(email='demo@mealmate.app').first()
        if not demo_user:
            demo_user = User()
            demo_user.id = f"demo_user_{str(hash('demo@mealmate.app'))[:8]}"
            demo_user.email = 'demo@mealmate.app'
            demo_user.first_name = 'Demo'
            demo_user.last_name = 'User'
            demo_user.email_verified = True
            demo_user.oauth_provider = None
            # No password hash - demo account doesn't need password

            db.session.add(demo_user)
            db.session.commit()

            # Create user directory
            user_dir = f"user_data/{demo_user.id}"
            os.makedirs(user_dir, exist_ok=True)
            os.makedirs(f"{user_dir}/saved_recipes", exist_ok=True)

            # Create default folder
            from folder_manager import FolderManager
            user_folder_manager = FolderManager(
                folders_file=f"user_data/{demo_user.id}/folders.json",
                recipes_dir=f"user_data/{demo_user.id}/saved_recipes")
            user_folder_manager.create_folder("Uncategorized")

        login_user(demo_user)
        flash('Welcome to MealMate Demo!', 'info')
        logging.info("Demo user logged in")

        return redirect(url_for('index'))

    except Exception as e:
        logging.error(f"Demo login error: {e}")
        flash('Demo login failed. Please try again.', 'error')
        return redirect(url_for('index'))


# API endpoint for checking authentication status
@auth_bp.route('/api/status')
def auth_status():
    """Return current authentication status"""
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'user': {
                'id': current_user.id,
                'email': current_user.email,
                'name': current_user.full_name
            }
        })
    else:
        return jsonify({'authenticated': False})
