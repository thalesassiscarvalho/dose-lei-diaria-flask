# -*- coding: utf-8 -*-
import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, redirect, url_for, render_template, flash
from flask_login import current_user
from sqlalchemy import text, inspect
from sqlalchemy.exc import OperationalError
import logging
from dotenv import load_dotenv

# ALTERADO: Importa 'mail' junto com as outras extensões
from src.extensions import db, migrate, csrf, login_manager, mail

# --- IMPORTAÇÃO DE MODELOS ---
from src.models.user import User, Achievement
from src.models.law import Law
from src.models.progress import UserProgress
from src.models.comment import UserComment
from src.models.study import StudySession
from src.models.product import Product
# --- FIM DA IMPORTAÇÃO DE MODELOS ---

from src.routes.auth import auth_bp
from src.routes.admin import admin_bp
from src.routes.student import student_bp

import datetime

load_dotenv()
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__,
            static_folder=os.path.join(os.path.dirname(__file__), 'static'),
            template_folder=os.path.join(os.path.dirname(__file__), 'templates'))

# =====================================================================
# <<< INÍCIO DA ALTERAÇÃO: CARREGAR CONFIGURAÇÕES DE E-MAIL E SEGURANÇA >>>
# =====================================================================
# Lendo as chaves de segurança do arquivo .env
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY')
app.config['SECURITY_PASSWORD_SALT'] = os.environ.get('SECURITY_PASSWORD_SALT')

# Lendo a configuração do banco de dados
DATABASE_URL = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL

# Lendo as configurações de e-mail do arquivo .env usando suas variáveis
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 465))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'false').lower() in ['true', 'on', '1']
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'true').lower() in ['true', 'on', '1']
app.config['MAIL_USERNAME'] = os.environ.get('EMAIL_USER')
app.config['MAIL_PASSWORD'] = os.environ.get('EMAIL_PASS')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('EMAIL_USER')
# =====================================================================
# <<< FIM DA ALTERAÇÃO >>>
# =====================================================================


app.config['CSP_POLICY'] = {
    'default-src': ["'self'"],
    'script-src': [
        "'self'",
        "'unsafe-inline'", # Necessário para scripts inline, como o do Service Worker em base.html
        'https://cdn.jsdelivr.net', # Para Toastify JS, SweetAlert2 JS
        'https://cdn.tailwindcss.com',
        'https://cdn.quilljs.com',
        'https://cdn.tiny.cloud',
        'https://kit.fontawesome.com'
    ],
    'style-src': [
        "'self'",
        "'unsafe-inline'", # Necessário para estilos inline
        'https://cdn.jsdelivr.net', # Para Toastify CSS
        'https://cdnjs.cloudflare.com', # Para Font Awesome CSS, Animate.css
        'https://cdn.quilljs.com', # Para Quill CSS
        'https://cdn.tiny.cloud',
        'https://fonts.googleapis.com',
        'https://ka-f.fontawesome.com'
    ],
    'font-src': [
        "'self'",
        'https://cdnjs.cloudflare.com', # Para Font Awesome webfonts
        'https://fonts.gstatic.com',
        'https://ka-f.fontawesome.com'
    ],
    'img-src': [
        "'self'",
        'data:', # Permite imagens base64
        'https://cdn.tiny.cloud'
    ],
    'media-src': [
        "'self'",
        'https://audios-estudoleieca.s3.us-west-2.amazonaws.com' # Para os arquivos de áudio das ondas neurais
    ],
    'connect-src': [
        "'self'",
        'https://cdn.tiny.cloud',
        'https://ka-f.fontawesome.com',
        'https://cdn.jsdelivr.net', # Adicionado para Toastify JS, SweetAlert2 JS (fetch)
        'https://cdnjs.cloudflare.com', # Adicionado para FontAwesome CSS/Webfonts (fetch)
        'https://cdn.quilljs.com', # Adicionado para Quill CSS (fetch)
        'https://audios-estudoleieca.s3.us-west-2.amazonaws.com' # Adicionado para os áudios das ondas neurais (fetch)
    ],
    'frame-ancestors': ["'none'"], # Impede que a página seja incorporada em iframes
    'object-src': ["'none'"], # Impede a carga de plugins como Flash
    'form-action': ["'self'"], # Restringe URLs que podem ser usadas como destinos para envios de formulário
    'base-uri': ["'self'"] # Restringe as URLs que podem aparecer no atributo <base> do documento
}

# --- Inicialização das Extensões com o App ---
# As instâncias são importadas de src.extensions e inicializadas aqui.
db.init_app(app)
migrate.init_app(app, db)
csrf.init_app(app)
login_manager.init_app(app)
mail.init_app(app) # <<< ADICIONADO: Inicializa o Flask-Mail com as configurações acima
# --- Fim da Inicialização ---

def ensure_achievements_exist():
    """Checks for predefined achievements and creates them if they don't exist."""
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

# Bloco de inicialização com a indentação corrigida
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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.after_request
def apply_csp(response):
    """
    Aplica o cabeçalho Content-Security-Policy lendo a política
    definida na configuração do app.
    """
    policy = app.config.get('CSP_POLICY', {})

    csp_header_value = "; ".join([
        f"{key} {' '.join(values)}" for key, values in policy.items()
    ])

    response.headers['Content-Security-Policy'] = csp_header_value
    return response

# --- Register Blueprints ---
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(admin_bp)
app.register_blueprint(student_bp)

# --- Main Routes ---
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

# Adicione esta rota para servir o favicon.ico
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
