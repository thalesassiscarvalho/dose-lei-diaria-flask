# main.py

# -*- coding: utf-8 -*-
import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, redirect, url_for, render_template, flash
from flask_login import LoginManager, current_user
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
import logging
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from dotenv import load_dotenv
import datetime

# --- INÍCIO DA CORREÇÃO DAS IMPORTAÇÕES ---
# 1. Importamos as extensões centralizadas.
from src.extensions import db, mail

# 2. Importamos APENAS os modelos, sem o 'db' junto.
from src.models.user import User, Achievement
from src.models.law import Law
from src.models.progress import UserProgress
from src.models.comment import UserComment
from src.models.study import StudySession

# 3. Importamos as rotas (blueprints).
from src.routes.auth import auth_bp
from src.routes.admin import admin_bp
from src.routes.student import student_bp
# --- FIM DA CORREÇÃO DAS IMPORTAÇÕES ---

load_dotenv()

logging.basicConfig(level=logging.DEBUG)

# --- CRIAÇÃO E CONFIGURAÇÃO DA APLICAÇÃO ---
app = Flask(__name__, 
            static_folder=os.path.join(os.path.dirname(__file__), 'static'),
            template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY')
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")

# --- CONFIGURAÇÃO PARA RECUPERAÇÃO DE SENHA ---
# Mantemos as configs aqui para consistência
app.config['SECURITY_PASSWORD_SALT'] = os.environ.get('SECURITY_PASSWORD_SALT')
app.config['MAIL_SERVER'] = 'smtp.hostinger.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.environ.get('EMAIL_USER')
app.config['MAIL_PASSWORD'] = os.environ.get('EMAIL_PASS')


# --- POLÍTICA DE SEGURANÇA ---
app.config['CSP_POLICY'] = {
    'default-src': ["'self'"],
    'script-src': [
        "'self'", "'unsafe-inline'", 'https://cdn.jsdelivr.net', 'https://cdn.tailwindcss.com',
        'https://cdn.quilljs.com', 'https://cdn.tiny.cloud', 'https://kit.fontawesome.com'
    ],
    'style-src': [
        "'self'", "'unsafe-inline'", 'https://cdn.jsdelivr.net', 'https://cdnjs.cloudflare.com',
        'https://cdn.quilljs.com', 'https://cdn.tiny.cloud', 'https://fonts.googleapis.com',
        'https://ka-f.fontawesome.com'
    ],
    'font-src': ["'self'", 'https://cdnjs.cloudflare.com', 'https://fonts.gstatic.com', 'https://ka-f.fontawesome.com'],
    'img-src': ["'self'", 'data:', 'https://cdn.tiny.cloud'],
    'media-src': ["'self'", 'https://audios-estudoleieca.s3.us-west-2.amazonaws.com'],
    'connect-src': [
        "'self'", 'https://cdn.tiny.cloud', 'https://ka-f.fontawesome.com', 'https://cdn.jsdelivr.net',
        'https://cdnjs.cloudflare.com', 'https://cdn.quilljs.com', 'https://audios-estudoleieca.s3.us-west-2.amazonaws.com'
    ],
    'frame-ancestors': ["'none'"], 'object-src': ["'none'"],
    'form-action': ["'self'"], 'base-uri': ["'self'"]
}

# --- INICIALIZAÇÃO DAS EXTENSÕES ---
# Conecta os objetos db e mail com a nossa aplicação 'app'
db.init_app(app)
mail.init_app(app) 
migrate = Migrate(app, db)
csrf = CSRFProtect(app)

# --- FUNÇÕES DE INICIALIZAÇÃO (como ensure_achievements_exist) ---
# Mantenha esta seção como estava no seu arquivo original, se houver.
# O código abaixo é baseado no que você enviou anteriormente.
def ensure_achievements_exist():
    """Verifica e cria as conquistas padrão se não existirem."""
    with app.app_context(): # Garante que estamos no contexto da aplicação
        logging.debug("Ensuring base achievements exist...")
        achievements_data = [
            {"name": "Primeiro Passo", "description": "Parabéns! Você começou sua jornada.", "laws_completed_threshold": 5, "icon": "fas fa-shoe-prints"},
            {"name": "Estudante Dedicado", "description": "O esforço já é visível. Parabéns pela constância!", "laws_completed_threshold": 10, "icon": "fas fa-book-reader"},
            # ... (e as outras conquistas)
        ]
        
        achievements_added = 0
        for data in achievements_data:
            existing_achievement = Achievement.query.filter_by(name=data["name"]).first()
            if not existing_achievement:
                achievement = Achievement(
                    name=data["name"],
                    description=data["description"],
                    laws_completed_threshold=data["laws_completed_threshold"],
                    icon=data.get("icon")
                )
                db.session.add(achievement)
                achievements_added += 1
        
        if achievements_added > 0:
            db.session.commit()

# --- LOGIN MANAGER ---
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
    
@app.after_request
def apply_csp(response):
    policy = app.config.get('CSP_POLICY', {})
    csp_header_value = "; ".join([f"{key} {' '.join(values)}" for key, values in policy.items()])
    response.headers['Content-Security-Policy'] = csp_header_value
    return response

# --- REGISTRO DE BLUEPRINTS ---
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(admin_bp)
app.register_blueprint(student_bp)

# --- ROTAS PRINCIPAIS ---
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for('admin.dashboard'))
        else:
            if not current_user.is_approved:
                 flash("Sua conta ainda não foi aprovada. Por favor, aguarde.", "warning")
                 return redirect(url_for('auth.login'))
            return redirect(url_for('student.dashboard'))
    return redirect(url_for('auth.login'))

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.context_processor
def inject_now():
    return {'now': datetime.datetime.utcnow()}

# Bloco para criar usuário admin e conquistas na inicialização
with app.app_context():
    try:
        db.create_all()
        admin_email = "thalesz@example.com"
        admin_user = User.query.filter_by(email=admin_email).first()
        if not admin_user:
            admin_user = User(email=admin_email, role='admin', is_approved=True, full_name='Admin User')
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
        ensure_achievements_exist()
    except Exception as e:
        logging.error(f"An error occurred during initial setup: {e}")
        db.session.rollback()


if __name__ == '__main__':
    app.run(debug=True)
