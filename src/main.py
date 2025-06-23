# main.py

# -*- coding: utf-8 -*-
import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, redirect, url_for, render_template, flash
from flask_login import LoginManager, current_user
from sqlalchemy import text, inspect
from sqlalchemy.exc import OperationalError
import logging
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from dotenv import load_dotenv
from flask_mail import Mail

load_dotenv()

# --- IMPORTAÇÃO DOS MODELOS E BLUEPRINTS ---
from src.models.user import db, User, Achievement
from src.models.law import Law
from src.models.progress import UserProgress
from src.models.comment import UserComment
from src.models.study import StudySession
from src.routes.auth import auth_bp
from src.routes.admin import admin_bp
from src.routes.student import student_bp
import datetime

logging.basicConfig(level=logging.DEBUG)

# --- CRIAÇÃO E CONFIGURAÇÃO DA APLICAÇÃO ---
app = Flask(__name__, 
            static_folder=os.path.join(os.path.dirname(__file__), 'static'),
            template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY')
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")

# --- CONFIGURAÇÃO PARA RECUPERAÇÃO DE SENHA ---
app.config['SECURITY_PASSWORD_SALT'] = os.environ.get('SECURITY_PASSWORD_SALT')
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't']
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
db.init_app(app)
mail = Mail(app)
migrate = Migrate(app, db)
csrf = CSRFProtect()
csrf.init_app(app)

# --- FUNÇÕES DE INICIALIZAÇÃO ---
def ensure_achievements_exist():
    """Verifica e cria as conquistas padrão se não existirem."""
    logging.debug("Ensuring base achievements exist...")
    achievements_data = [
        {"name": "Primeiro Passo", "description": "Parabéns! Você começou sua jornada.", "laws_completed_threshold": 5, "icon": "fas fa-shoe-prints"},
        {"name": "Estudante Dedicado", "description": "O esforço já é visível. Parabéns pela constância!", "laws_completed_threshold": 10, "icon": "fas fa-book-reader"},
        {"name": "Leitor de Leis", "description": "Agora você é um verdadeiro decifrador de artigos.", "laws_completed_threshold": 20, "icon": "fas fa-glasses"},
        {"name": "Operador do Saber", "description": "Seu conhecimento começa a operar mudanças.", "laws_completed_threshold": 30, "icon": "fas fa-cogs"},
        {"name": "Mestre em Formação", "description": "Sua bagagem está cada vez mais robusta.", "laws_completed_threshold": 50, "icon": "fas fa-graduation-cap"},
        {"name": "Mestre das Normas", "description": "Padrões, princípios e regras não têm segredos pra você.", "laws_completed_threshold": 75, "icon": "fas fa-balance-scale"},
        {"name": "Guardião das Leis", "description": "Sua dedicação é digna de uma toga.", "laws_completed_threshold": 100, "icon": "fas fa-gavel"},
        {"name": "Mentor da Lei", "description": "Você inspira outros estudantes a seguirem seu exemplo.", "laws_completed_threshold": 150, "icon": "fas fa-chalkboard-teacher"},
        {"name": "Uma lenda!", "description": "Um verdadeiro mito entre os estudiosos.", "laws_completed_threshold": 200, "icon": "fas fa-crown"}
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
            logging.debug(f"Adding achievement: {data['name']}")
    
    if achievements_added > 0:
        try:
            db.session.commit()
            logging.info(f"{achievements_added} achievements successfully added.")
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding achievements during initialization: {e}")
    else:
        logging.debug("All base achievements already exist.")

with app.app_context():
    logging.info("Initializing database (manual checks)...")
    try:
        db.create_all()
        logging.info("Database tables ensured (created if they didn't exist).")

        admin_email = "thalesz@example.com"
        logging.debug(f"Checking for admin user with email: {admin_email}")
        admin_user = User.query.filter_by(email=admin_email).first()

        if not admin_user:
            logging.info(f"Admin user not found. Creating new admin user...")
            admin_user = User(email=admin_email, role='admin', is_approved=True, full_name='Admin User')
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            try:
                db.session.commit()
                logging.info(f"Default admin user created and committed successfully.")
            except Exception as commit_error:
                db.session.rollback()
                logging.error(f"ERROR committing new admin user: {commit_error}")
        else:
            logging.debug(f"Admin user found. ID: {admin_user.id}")

        ensure_achievements_exist()

    except Exception as e:
        logging.error(f"An error occurred during database initialization: {e}")
        db.session.rollback()

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
    return {'now': datetime.datetime.utcnow}

with app.app_context():
    try:
        db.session.execute(text("SELECT 1"))
        logging.info("✅ Conexão com o banco de dados bem-sucedida!")
    except Exception as e:
        logging.error(f"❌ Falha na conexão com o banco de dados: {e}")

if __name__ == '__main__':
    app.run(debug=True)
