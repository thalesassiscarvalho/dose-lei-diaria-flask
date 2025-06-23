# src/routes/auth.py

# -*- coding: utf-8 -*-
import os
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from werkzeug.security import check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
import logging
import bleach
from itsdangerous import URLSafeTimedSerializer, SignatureExpired

# --- NOVAS IMPORTAÇÕES PARA O E-MAIL ---
import smtplib
from email.message import EmailMessage

from src.models.user import db, User


logging.basicConfig(level=logging.DEBUG)
auth_bp = Blueprint("auth", __name__)


def generate_password_reset_token(email):
    """Gera um token seguro para a redefinição de senha."""
    serializer = URLSafeTimedSerializer(os.environ.get('FLASK_SECRET_KEY'))
    return serializer.dumps(email, salt=os.environ.get('SECURITY_PASSWORD_SALT'))

def confirm_reset_token(token, expiration=3600):
    """Verifica o token. Retorna o e-mail se for válido, ou None se inválido/expirado."""
    serializer = URLSafeTimedSerializer(os.environ.get('FLASK_SECRET_KEY'))
    try:
        email = serializer.loads(
            token,
            salt=os.environ.get('SECURITY_PASSWORD_SALT'),
            max_age=expiration
        )
        return email
    except (SignatureExpired, Exception):
        return None

# ... (As rotas /login, /signup, /logout permanecem exatamente as mesmas) ...
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        else:
            return redirect(url_for("student.dashboard"))

    if request.method == "POST":
        email = bleach.clean(request.form.get("email"), tags=[], strip=True)
        password = request.form.get("password")
        remember = True if request.form.get("remember") else False
        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash("Email ou senha inválidos.", "danger")
            return redirect(url_for("auth.login"))

        if user.role != "admin" and not user.is_approved:
            flash("Sua conta ainda não foi aprovada por um administrador.", "warning")
            return redirect(url_for("auth.login"))

        login_user(user, remember=remember)
        flash("Login realizado com sucesso!", "success")

        if user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        else:
            return redirect(url_for("student.dashboard"))

    return render_template("login.html")

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("student.dashboard"))

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
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash("Conta criada com sucesso! Aguarde a aprovação do administrador para fazer login.", "info")
            return redirect(url_for("auth.login"))
        except Exception as e:
            db.session.rollback()
            flash("Erro ao criar conta. Tente novamente.", "danger")
            return redirect(url_for("auth.signup"))

    return render_template("signup.html")
    
@auth_bp.route("/logout")
@login_required
def logout():
    user_email = current_user.email
    logout_user()
    flash("Você foi desconectado.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('student.dashboard'))

    if request.method == 'POST':
        email = bleach.clean(request.form.get('email'), tags=[], strip=True)
        user = User.query.filter_by(email=email).first()

        if user:
            logging.debug(f"[AUTH DEBUG] Password reset requested for existing user: {email}")
            try:
                # --- INÍCIO DO NOVO CÓDIGO DE ENVIO ---
                token = generate_password_reset_token(email)
                reset_url = url_for('auth.reset_with_token', token=token, _external=True)
                html_body = render_template('email/reset_password_email.html', reset_url=reset_url)

                # Pega as credenciais do ambiente
                EMAIL_HOST = 'smtp.hostinger.com'
                EMAIL_PORT = 465
                SENDER_EMAIL = os.environ.get('EMAIL_USER')
                SENDER_PASS = os.environ.get('EMAIL_PASS')

                # Cria a mensagem de e-mail
                msg = EmailMessage()
                msg['Subject'] = 'Redefinição de Senha - Estudo da Lei Seca'
                msg['From'] = SENDER_EMAIL
                msg['To'] = email
                msg.set_content('Não foi possível carregar o conteúdo HTML.') # Fallback
                msg.add_alternative(html_body, subtype='html')

                # Conecta, autentica e envia usando o método que funcionou
                with smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT) as server:
                    server.login(SENDER_EMAIL, SENDER_PASS)
                    server.send_message(msg)
                
                logging.info(f"[AUTH DEBUG] Password reset email sent to: {email} using smtplib.")
                # --- FIM DO NOVO CÓDIGO DE ENVIO ---

            except Exception as e:
                logging.error(f"[AUTH ERROR] Failed to send password reset email to {email}: {e}")
                flash('Ocorreu um erro ao enviar o e-mail. Por favor, tente novamente mais tarde.', 'danger')
                return redirect(url_for('auth.forgot_password'))
        else:
            logging.warning(f"[AUTH DEBUG] Password reset requested for non-existent user: {email}")
        
        flash('Se um e-mail correspondente for encontrado em nosso sistema, um link de recuperação será enviado.', 'info')
        return redirect(url_for('auth.login'))
            
    return render_template("forgot_password.html")

# ... (A rota /reset-password/<token> permanece exatamente a mesma) ...
@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_with_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('student.dashboard'))
        
    email = confirm_reset_token(token)
    if not email:
        flash('O link de redefinição de senha é inválido ou expirou.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not password or password != confirm_password:
            flash('As senhas não conferem ou estão em branco. Tente novamente.', 'danger')
            return redirect(url_for('auth.reset_with_token', token=token))
        
        if len(password) < 6:
            flash('Sua senha precisa ter no mínimo 6 caracteres.', 'danger')
            return redirect(url_for('auth.reset_with_token', token=token))

        user = User.query.filter_by(email=email).first()
        if user:
            try:
                user.set_password(password)
                db.session.commit()
                flash('Sua senha foi redefinida com sucesso! Você já pode fazer o login.', 'success')
                return redirect(url_for('auth.login'))
            except Exception as e:
                db.session.rollback()
                flash('Ocorreu um erro ao salvar sua nova senha. Tente novamente.', 'danger')
                return redirect(url_for('auth.reset_with_token', token=token))

    return render_template("reset_password_from_token.html", token=token)
