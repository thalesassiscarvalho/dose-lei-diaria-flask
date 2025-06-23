# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from src.extensions import db
from src.models.user import User
import logging
# NOVO: Importar a biblioteca de sanitização
import bleach

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
        # ALTERADO: Sanitiza o email para remover qualquer tag HTML
        email = bleach.clean(request.form.get("email"), tags=[], strip=True)
        password = request.form.get("password")
        remember = True if request.form.get("remember") else False
        logging.debug(f"[AUTH DEBUG] Login attempt for email: {email}")

        user = User.query.filter_by(email=email).first()

        if user:
            logging.debug(f"[AUTH DEBUG] User found: ID={user.id}, Email={user.email}, Role={user.role}, Hash={user.password_hash}")
            password_check_result = user.check_password(password)
            logging.debug(f"[AUTH DEBUG] Password check result for 	'{password}	': {password_check_result}")
        else:
            logging.debug(f"[AUTH DEBUG] User not found for email: {email}")

        if not user or not user.check_password(password):
            logging.warning(f"[AUTH DEBUG] Invalid login attempt for email: {email}")
            flash("Email ou senha inválidos.", "danger")
            return redirect(url_for("auth.login"))

        if user.role != "admin" and not user.is_approved:
            logging.warning(f"[AUTH DEBUG] Unapproved user login attempt: {email}")
            flash("Sua conta ainda não foi aprovada por um administrador.", "warning")
            return redirect(url_for("auth.login"))

        login_user(user, remember=remember)
        logging.info(f"[AUTH DEBUG] User logged in successfully: {email}")
        flash("Login realizado com sucesso!", "success")

        if user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        else:
            return redirect(url_for("student.dashboard"))
            
    # ALTERADO: Aponta para o novo caminho do template
    return render_template("auth/login.html")

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        # ALTERADO: Sanitiza todos os campos de texto do formulário
        email = bleach.clean(request.form.get("email"), tags=[], strip=True)
        full_name = bleach.clean(request.form.get("full_name"), tags=[], strip=True)
        phone = bleach.clean(request.form.get("phone"), tags=[], strip=True)
        password = request.form.get("password")

        if not email or not full_name or not phone or not password:
            flash("Todos os campos são obrigatórios.", "danger")
            return redirect(url_for("auth.signup"))

        user = User.query.filter_by(email=email).first()

        if user:
            flash("Este email já está cadastrado.", "warning")
            return redirect(url_for("auth.signup"))

        new_user = User(email=email, full_name=full_name, phone=phone, role="student", is_approved=False)
        new_user.set_password(password)
        logging.debug(f"[AUTH DEBUG] Creating new user: {email}, Hash: {new_user.password_hash}")

        try:
            db.session.add(new_user)
            db.session.commit()
            logging.info(f"[AUTH DEBUG] New user created successfully: {email}")
            flash("Conta criada com sucesso! Aguarde a aprovação do administrador para fazer login.", "info")
            return redirect(url_for("auth.login"))
        except Exception as e:
            db.session.rollback()
            logging.error(f"[AUTH DEBUG] Error creating user {email}: {e}")
            flash("Erro ao criar conta. Tente novamente.", "danger")
            return redirect(url_for("auth.signup"))

    # ALTERADO: Aponta para o novo caminho do template
    return render_template("auth/signup.html")
    
@auth_bp.route("/logout")
@login_required
def logout():
    user_email = current_user.email
    logout_user()
    logging.info(f"[AUTH DEBUG] User logged out: {user_email}")
    flash("Você foi desconectado.", "info")
    return redirect(url_for("auth.login"))
