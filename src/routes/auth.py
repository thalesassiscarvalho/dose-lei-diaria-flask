# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from src.models.user import db, User
import logging # Import logging

# Configure basic logging
logging.basicConfig(level=logging.DEBUG)

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        logging.debug(f"[AUTH DEBUG] User already authenticated: {current_user.email}. Redirecting...")
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        else:
            return redirect(url_for("student.dashboard"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        remember = True if request.form.get("remember") else False
        logging.debug(f"[AUTH DEBUG] Login attempt for email: {email}") # ADDED LOG

        # Query user by email
        user = User.query.filter_by(email=email).first()

        if user:
            logging.debug(f"[AUTH DEBUG] User found: ID={user.id}, Email={user.email}, Role={user.role}, Hash={user.password_hash}") # ADDED LOG
            password_check_result = user.check_password(password)
            logging.debug(f"[AUTH DEBUG] Password check result for 	'{password}	': {password_check_result}") # ADDED LOG
        else:
            logging.debug(f"[AUTH DEBUG] User not found for email: {email}") # ADDED LOG

        # Check if user exists and password is correct
        if not user or not user.check_password(password): # Using the variable from above might be slightly more efficient but this is clearer for debug
            logging.warning(f"[AUTH DEBUG] Invalid login attempt for email: {email}") # ADDED LOG
            flash("Email ou senha inválidos.", "danger")
            return redirect(url_for("auth.login"))

        # Check if the user is approved (skip check for admin)
        # The logic below had a specific check for 'admin@dose.lei' which is outdated.
        # Let's simplify: if the role is 'admin', approval is not needed.
        if user.role != "admin" and not user.is_approved:
            logging.warning(f"[AUTH DEBUG] Unapproved user login attempt: {email}") # ADDED LOG
            flash("Sua conta ainda não foi aprovada por um administrador.", "warning")
            return redirect(url_for("auth.login"))

        # Log the user in
        login_user(user, remember=remember)
        logging.info(f"[AUTH DEBUG] User logged in successfully: {email}") # ADDED LOG
        flash("Login realizado com sucesso!", "success")

        # Redirect to appropriate dashboard based on role
        if user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        else:
            return redirect(url_for("student.dashboard"))

    # GET request: render the login template
    return render_template("login.html")

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("main.index")) # Redirect if already logged in

    if request.method == "POST":
        email = request.form.get("email")
        full_name = request.form.get("full_name")
        phone = request.form.get("phone")
        password = request.form.get("password")

        # Check if email already exists
        user = User.query.filter_by(email=email).first()

        if user:
            flash("Este email já está cadastrado.", "warning")
            return redirect(url_for("auth.signup"))

        # Create new user (student role, not approved by default)
        new_user = User(email=email, full_name=full_name, phone=phone, role="student", is_approved=False)
        new_user.set_password(password)
        logging.debug(f"[AUTH DEBUG] Creating new user: {email}, Hash: {new_user.password_hash}") # ADDED LOG

        try: # ADDED TRY/EXCEPT
            db.session.add(new_user)
            db.session.commit()
            logging.info(f"[AUTH DEBUG] New user created successfully: {email}") # ADDED LOG
            flash("Conta criada com sucesso! Aguarde a aprovação do administrador para fazer login.", "info")
            return redirect(url_for("auth.login"))
        except Exception as e: # ADDED EXCEPTION HANDLING
            db.session.rollback()
            logging.error(f"[AUTH DEBUG] Error creating user {email}: {e}") # ADDED LOG
            flash("Erro ao criar conta. Tente novamente.", "danger")
            return redirect(url_for("auth.signup"))

    # GET request: render the signup template
    return render_template("signup.html")

@auth_bp.route("/logout")
@login_required
def logout():
    user_email = current_user.email # Get email before logging out
    logout_user()
    logging.info(f"[AUTH DEBUG] User logged out: {user_email}") # ADDED LOG
    flash("Você foi desconectado.", "info")
    return redirect(url_for("auth.login"))

