# -*- coding: utf-8 -*-
import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, redirect, url_for, render_template, flash # Import flash
from flask_login import LoginManager, current_user
from sqlalchemy import text, inspect # Import text for raw SQL and inspect for introspection
from sqlalchemy.exc import OperationalError # Import exception for handling errors
import logging # Import logging
from flask_wtf.csrf import CSRFProtect # Importação do CSRFProtect

# --- NOVO: Importar Flask-Migrate ---
from flask_migrate import Migrate
# --- FIM NOVO ---

from dotenv import load_dotenv
load_dotenv()

# Import models and db instance
from src.models.user import db, User, Achievement # Import Achievement
from src.models.law import Law
from src.models.progress import UserProgress
from src.models.comment import UserComment

# Import blueprints
from src.routes.auth import auth_bp
from src.routes.admin import admin_bp
from src.routes.student import student_bp

# Configure basic logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__, 
            static_folder=os.path.join(os.path.dirname(__file__), 'static'),
            template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY') # Use environment variable for secret key

# --- Database Configuration ---
# Use environment variables for database credentials for security
DATABASE_URL = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
db.init_app(app)

# --- NOVO: Inicializar Flask-Migrate ---
migrate = Migrate(app, db)
# --- FIM NOVO ---

# --- NOVO: Inicializar CSRFProtect ---
csrf = CSRFProtect()
csrf.init_app(app)
# --- FIM NOVO ---

# --- Function to Ensure Achievements Exist ---
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
        # else: # Optional: Log if it already exists
            # logging.debug(f"Achievement '{data['name']}' already exists.")
    
    if achievements_added > 0:
        try:
            db.session.commit()
            logging.info(f"{achievements_added} achievements successfully added.")
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding achievements during initialization: {e}")
    else:
        logging.debug("All base achievements already exist.")

# --- Database Initialization and Migration (Manual/Basic) --- 
# Note: This section performs basic checks and ALTER TABLE commands.
# It's generally recommended to use Flask-Migrate for more robust migrations,
# but this code attempts manual adjustments.
# The Flask-Migrate commands (flask db migrate/upgrade) should be run separately
# after initializing Migrate above.
with app.app_context():
    logging.info("Initializing database (manual checks)...")
    try:
        # Ensure tables exist (create_all is generally safe)
        db.create_all()
        logging.info("Database tables ensured (created if they didn't exist).")

        # --- Admin User Creation/Check --- 
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
            # ... (rest of admin check logic)

        # --- Ensure Base Achievements Exist ---
        ensure_achievements_exist()

    except Exception as e:
        logging.error(f"An error occurred during database initialization: {e}")
        db.session.rollback() # Rollback any partial changes on error

# --- Flask-Login Configuration ---
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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

# Serve static files (If needed, usually handled by web server in production)
# @app.route('/<path:path>')
# def serve_static_or_index(path):
#     # ... (static file serving logic)

# Add context processor for footer year
import datetime
@app.context_processor
def inject_now():
    return {'now': datetime.datetime.utcnow}

# --- Database Connection Check --- 
# (Removed the manual migration logic from here as Flask-Migrate handles it)
with app.app_context():
    try:
        db.session.execute(text("SELECT 1"))
        logging.info("✅ Conexão com o banco de dados bem-sucedida!")
    except Exception as e:
        logging.error(f"❌ Falha na conexão com o banco de dados: {e}")

if __name__ == '__main__':
    # Note: Use a proper WSGI server like Gunicorn in production
    app.run(debug=True) # debug=True is NOT for production
