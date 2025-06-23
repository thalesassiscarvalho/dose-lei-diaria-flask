# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from src.extensions import db, mail
from src.models.user import User
import logging
import bleach
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
# <<< NOVA IMPORTAÇÃO PARA CORRIGIR O ERRO DA DATA >>>
import datetime


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
            
    return render_template("auth/login.html")

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
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

    return render_template("auth/signup.html")
    
@auth_bp.route("/logout")
@login_required
def logout():
    user_email = current_user.email
    logout_user()
    logging.info(f"[AUTH DEBUG] User logged out: {user_email}")
    flash("Você foi desconectado.", "info")
    return redirect(url_for("auth.login"))


# =====================================================================
# <<< INÍCIO DO NOVO CÓDIGO PARA RECUPERAÇÃO DE SENHA >>>
# =====================================================================

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("student.dashboard"))

    if request.method == "POST":
        email = bleach.clean(request.form.get("email"), tags=[], strip=True)
        user = User.query.filter_by(email=email).first()

        # Mesmo se o usuário não existir, não informamos isso por segurança.
        if user:
            # Gerar o token seguro
            serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            token = serializer.dumps(email, salt=current_app.config['SECURITY_PASSWORD_SALT'])

            # Criar o link de redefinição
            reset_url = url_for('auth.reset_with_token', token=token, _external=True)

            # Preparar e enviar o e-mail
            # =====================================================================
            # <<< INÍCIO DA ALTERAÇÃO: Passando o ano para o template >>>
            # =====================================================================
            current_year = datetime.datetime.now().year
            msg = Message(
                subject="Redefinição de Senha - Dose de Lei Diária",
                sender=current_app.config['MAIL_DEFAULT_SENDER'],
                recipients=[email]
            )
            msg.html = render_template(
                'auth/reset_password_email.html', 
                reset_url=reset_url, 
                current_year=current_year # <-- Enviando o ano para o template
            )
            # =====================================================================
            # <<< FIM DA ALTERAÇÃO >>>
            # =====================================================================
            
            try:
                mail.send(msg)
            except Exception as e:
                logging.error(f"[AUTH DEBUG] Falha ao enviar e-mail de redefinição para {email}: {e}")
                flash("Ocorreu um erro ao tentar enviar o e-mail. Tente novamente mais tarde.", "danger")
                return redirect(url_for('auth.forgot_password'))

        flash("Se um usuário com este e-mail existir, um link de redefinição de senha foi enviado.", "info")
        return redirect(url_for('auth.login'))

    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_with_token(token):
    if current_user.is_authenticated:
        return redirect(url_for("student.dashboard"))

    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        # Tenta decodificar o token (válido por 1 hora = 3600s)
        email = serializer.loads(
            token,
            salt=current_app.config['SECURITY_PASSWORD_SALT'],
            max_age=3600
        )
    except (SignatureExpired, BadTimeSignature):
        flash("O link de redefinição de senha é inválido ou expirou.", "danger")
        return redirect(url_for('auth.forgot_password'))

    if request.method == "POST":
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if not new_password or new_password != confirm_password:
            flash("As senhas não conferem ou estão vazias. Tente novamente.", "danger")
            return render_template("auth/reset_password_from_token.html", token=token)

        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(new_password)
            db.session.commit()
            flash("Sua senha foi redefinida com sucesso! Você já pode fazer o login.", "success")
            return redirect(url_for('auth.login'))

    return render_template("auth/reset_password_from_token.html", token=token)

# =====================================================================
# <<< FIM DO NOVO CÓDIGO >>>
# =====================================================================
