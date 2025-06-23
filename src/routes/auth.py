# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from src.extensions import db, mail
from src.models.user import User
import logging
import bleach
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
import datetime

# =====================================================================
# <<< INÍCIO DA ALTERAÇÃO: Novas importações para o 2FA por E-mail >>>
# =====================================================================
import secrets
from datetime import datetime, timedelta
# =====================================================================
# <<< FIM DA ALTERAÇÃO >>>
# =====================================================================


logging.basicConfig(level=logging.DEBUG)

auth_bp = Blueprint("auth", __name__)

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

        # =====================================================================
        # <<< INÍCIO DA ALTERAÇÃO: LÓGICA DE 2FA POR E-MAIL >>>
        # =====================================================================
        # Se o usuário for um administrador, iniciamos o fluxo de 2FA.
        if user.role == 'admin':
            # 1. Gera um código seguro de 6 dígitos
            auth_code = str(secrets.randbelow(1000000)).zfill(6)
            
            # 2. Guarda o código e outras informações na sessão do navegador
            session['2fa_code'] = auth_code
            session['2fa_user_id'] = user.id
            session['2fa_expiry'] = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
            session['2fa_remember_me'] = remember

            # 3. Envia o e-mail com o código de verificação
            try:
                msg = Message(
                    subject="Seu Código de Verificação - Estudo da Lei Seca",
                    sender=current_app.config['MAIL_DEFAULT_SENDER'],
                    recipients=[user.email]
                )
                msg.body = f"Olá.\n\nSeu código de verificação para login é: {auth_code}\n\nEste código expira em 10 minutos."
                msg.html = f"<p>Olá.</p><p>Seu código de verificação para login é: <b>{auth_code}</b></p><p>Este código expira em 10 minutos.</p>"
                mail.send(msg)
                
                # 4. Redireciona para a página de verificação de código
                return redirect(url_for('auth.verify_email_code'))

            except Exception as e:
                logging.error(f"Falha ao enviar e-mail de 2FA para {user.email}: {e}")
                flash("Não foi possível enviar o código de verificação. Tente novamente mais tarde.", "danger")
                return redirect(url_for('auth.login'))
        # =====================================================================
        # <<< FIM DA ALTERAÇÃO >>>
        # =====================================================================

        # Se for um usuário comum, o login acontece normalmente.
        login_user(user, remember=remember)
        logging.info(f"[AUTH DEBUG] User logged in successfully: {email}")
        flash("Login realizado com sucesso!", "success")
        return redirect(url_for("student.dashboard"))
            
    return render_template("auth/login.html")


# =====================================================================
# <<< INÍCIO DA NOVA ROTA PARA VERIFICAR O CÓDIGO DE E-MAIL >>>
# =====================================================================
@auth_bp.route('/verify-email-code', methods=['GET', 'POST'])
def verify_email_code():
    # Se o usuário não estiver no meio do processo de 2FA, manda de volta para o login
    if '2fa_user_id' not in session:
        return redirect(url_for('auth.login'))
        
    # Verifica se o código na sessão já expirou
    expiry_time = datetime.fromisoformat(session['2fa_expiry'])
    if datetime.utcnow() > expiry_time:
        # Limpa a sessão e manda de volta pro login com um aviso
        session.pop('2fa_code', None)
        session.pop('2fa_user_id', None)
        session.pop('2fa_expiry', None)
        session.pop('2fa_remember_me', None)
        flash('O código de verificação expirou. Por favor, tente fazer o login novamente.', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        user_code = request.form.get('code')
        
        # Verifica se o código digitado é o mesmo que foi guardado na sessão
        if user_code == session.get('2fa_code'):
            user_id = session['2fa_user_id']
            remember = session['2fa_remember_me']
            user = User.query.get(user_id)
            
            # Limpa a sessão para que o código não possa ser reutilizado
            session.pop('2fa_code', None)
            session.pop('2fa_user_id', None)
            session.pop('2fa_expiry', None)
            session.pop('2fa_remember_me', None)

            if user:
                login_user(user, remember=remember)
                flash('Login realizado com sucesso!', 'success')
                return redirect(url_for('admin.dashboard'))
            else:
                flash('Ocorreu um erro. Usuário não encontrado.', 'danger')
                return redirect(url_for('auth.login'))
        else:
            flash('Código de verificação inválido.', 'danger')

    return render_template('auth/verify_email_code.html')
# =====================================================================
# <<< FIM DA NOVA ROTA >>>
# =====================================================================


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

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("student.dashboard"))
    if request.method == "POST":
        email = bleach.clean(request.form.get("email"), tags=[], strip=True)
        user = User.query.filter_by(email=email).first()
        if user:
            serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            token = serializer.dumps(email, salt=current_app.config['SECURITY_PASSWORD_SALT'])
            reset_url = url_for('auth.reset_with_token', token=token, _external=True)
            current_year = datetime.now().year
            msg = Message(
                subject="Redefinição de Senha - Estudo da Lei Seca",
                sender=current_app.config['MAIL_DEFAULT_SENDER'],
                recipients=[email]
            )
            msg.html = render_template(
                'auth/reset_password_email.html', 
                reset_url=reset_url, 
                current_year=current_year
            )
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
