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
from flask_migrate import Migrate  # <<< ADDED IMPORT

from dotenv import load_dotenv
load_dotenv()

# Import models and db instance
from src.models.user import db, User, Achievement
from src.models.law import Law, Subject
from src.models.progress import UserProgress

# Import blueprints
from src.routes.auth import auth_bp
from src.routes.admin import admin_bp
from src.routes.student import student_bp

# Configure basic logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__,
            static_folder=os.path.join(os.path.dirname(__file__), 'static'),
            template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY')

# --- Database Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL

# --- Upload Configuration ---
UPLOAD_FOLDER_BASE = os.path.join(app.root_path, 'static', 'uploads')
AUDIO_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER_BASE, 'audio')
app.config['UPLOAD_FOLDER'] = AUDIO_UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

if not os.path.exists(AUDIO_UPLOAD_FOLDER):
    try:
        os.makedirs(AUDIO_UPLOAD_FOLDER)
        logging.info(f"Upload folder created at: {AUDIO_UPLOAD_FOLDER}")
    except OSError as e:
        logging.error(f"Error creating upload folder {AUDIO_UPLOAD_FOLDER}: {e}")

db.init_app(app)
migrate = Migrate(app, db)  # <<< INITIALIZE FLASK-MIGRATE

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

    if achievements_added > 0:
        try:
            db.session.commit()
            logging.info(f"{achievements_added} achievements successfully added.")
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding achievements during initialization: {e}")
    else:
        logging.debug("All base achievements already exist.")

# --- Database Initialization and Migration --- 
with app.app_context():
    logging.info("Initializing database and running migrations...")
    try:
        db.create_all()
        logging.info("Database tables ensured (created if they didn't exist).")

        inspector = inspect(db.engine)

        # --- User Table Migrations (Existing code remains the same) ---
        user_columns = inspector.get_columns('user')
        user_column_names = [c['name'] for c in user_columns]

        if 'email' not in user_column_names:
            logging.info("Attempting to add 'email' column to user...")
            try:
                db.session.execute(text("ALTER TABLE user ADD COLUMN email VARCHAR(120)"))
                db.session.commit()
                logging.info("'email' column added (nullable).")
                if 'username' in user_column_names:
                    logging.info("Populating 'email' column from 'username'...")
                    update_sql = text("""
                        UPDATE user 
                        SET email = CASE 
                            WHEN username = 'admin' THEN 'thalesz@example.com' 
                            ELSE CONCAT(username, '@placeholder.email')
                        END 
                        WHERE email IS NULL
                    """)
                    db.session.execute(update_sql)
                    db.session.commit()
                    logging.info("'email' column populated.")
                db.session.execute(text("ALTER TABLE user MODIFY COLUMN email VARCHAR(120) NOT NULL UNIQUE"))
                db.session.commit()
                logging.info("'email' column is now NOT NULL UNIQUE.")
            except Exception as e:
                logging.error(f"Error during 'email' column migration: {e}")
                db.session.rollback()
        else:
             logging.debug("'email' column already exists in user.")

        if 'username' in user_column_names and 'email' in user_column_names:
             logging.info("Attempting to drop 'username' column from user...")
             try:
                 db.session.execute(text("ALTER TABLE user DROP COLUMN username"))
                 db.session.commit()
                 logging.info("'username' column dropped.")
             except Exception as e:
                 logging.warning(f"Warning: Error dropping 'username' column: {e}")
                 db.session.rollback()

        if 'is_approved' not in user_column_names:
            logging.info("Attempting to add 'is_approved' column to user...")
            try:
                db.session.execute(text("ALTER TABLE user ADD COLUMN is_approved BOOLEAN NOT NULL DEFAULT false"))
                db.session.commit()
                logging.info("'is_approved' column added.")
            except OperationalError as e:
                logging.error(f"Error adding 'is_approved' column: {e}")
                db.session.rollback()
        else:
            logging.debug("'is_approved' column already exists in user.")

        if 'full_name' not in user_column_names:
            logging.info("Attempting to add 'full_name' column to user...")
            try:
                db.session.execute(text("ALTER TABLE user ADD COLUMN full_name VARCHAR(120) NULL"))
                db.session.commit()
                logging.info("'full_name' column added successfully.")
            except OperationalError as e:
                logging.error(f"Error adding 'full_name' column: {e}")
                db.session.rollback()
        else:
            logging.debug("'full_name' column already exists in user.")

        if 'phone' not in user_column_names:
            logging.info("Attempting to add 'phone' column to user...")
            try:
                db.session.execute(text("ALTER TABLE user ADD COLUMN phone VARCHAR(20) NULL"))
                db.session.commit()
                logging.info("'phone' column added successfully.")
            except OperationalError as e:
                logging.error(f"Error adding 'phone' column: {e}")
                db.session.rollback()
        else:
            logging.debug("'phone' column already exists in user.")

        # --- User Progress Table Migrations (Existing code remains the same) ---
        progress_columns = inspector.get_columns('user_progress')
        progress_column_names = [c['name'] for c in progress_columns]

        if 'last_read_article' not in progress_column_names:
            logging.info("Attempting to add 'last_read_article' column to user_progress...")
            try:
                db.session.execute(text("ALTER TABLE user_progress ADD COLUMN last_read_article VARCHAR(50) NULL"))
                db.session.commit()
                logging.info("'last_read_article' column added successfully to user_progress.")
            except OperationalError as e:
                logging.error(f"Error adding 'last_read_article' column to user_progress: {e}")
                db.session.rollback()
        else:
            logging.debug("'last_read_article' column already exists in user_progress.")

        if 'status' not in progress_column_names:
            logging.info("Attempting to add 'status' column to user_progress...")
            try:
                alter_sql_add_status = text("ALTER TABLE user_progress ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'nao_iniciado'")
                db.session.execute(alter_sql_add_status)
                db.session.commit()
                logging.info("'status' column added successfully to user_progress with default 'nao_iniciado'.")

                logging.info("Updating existing user_progress statuses based on completed_at and last_read_article...")
                update_concluido_sql = text("UPDATE user_progress SET status = 'concluido' WHERE completed_at IS NOT NULL AND status = 'nao_iniciado'")
                update_andamento_sql = text("UPDATE user_progress SET status = 'em_andamento' WHERE completed_at IS NULL AND last_read_article IS NOT NULL AND status = 'nao_iniciado'")

                result_concluido = db.session.execute(update_concluido_sql)
                db.session.commit()
                logging.info(f"Updated {result_concluido.rowcount} rows to 'concluido'.")

                result_andamento = db.session.execute(update_andamento_sql)
                db.session.commit()
                logging.info(f"Updated {result_andamento.rowcount} rows to 'em_andamento'.")

                logging.info("Existing user_progress statuses updated.")

            except OperationalError as e:
                logging.error(f"Error adding or updating 'status' column in user_progress: {e}")
                db.session.rollback()
        else:
            logging.debug("'status' column already exists in user_progress.")

        # --- Admin User Creation/Check (Existing code remains the same) --- 
        admin_email = "thalesz@example.com"
        logging.debug(f"Checking for admin user with email: {admin_email}")
        admin_user = User.query.filter_by(email=admin_email).first()

        if not admin_user:
            logging.info(f"Admin user not found. Creating new admin user...")
            admin_user = User(email=admin_email, role='admin', is_approved=True, full_name='Admin User')
            admin_user.set_password('admin123')
            logging.debug(f"Admin password set. Hash generated: {admin_user.password_hash}")
            db.session.add(admin_user)
            try:
                db.session.commit()
                logging.info(f"Default admin user created and committed successfully.")
            except Exception as commit_error:
                db.session.rollback()
                logging.error(f"ERROR committing new admin user: {commit_error}")
        else:
            logging.debug(f"Admin user found. ID: {admin_user.id}, Email: {admin_user.email}, Hash: {admin_user.password_hash}")
            updated = False
            if not admin_user.is_approved:
                 logging.info(f"Ensuring admin user '{admin_email}' is approved...")
                 admin_user.is_approved = True
                 updated = True
            if not admin_user.full_name:
                 logging.info(f"Setting default name for admin user '{admin_email}'...")
                 admin_user.full_name = 'Admin User'
                 updated = True

            logging.debug(f"Checking if admin password needs reset (for debugging)...")
            if not admin_user.check_password('admin123'):
                logging.warning(f"Admin password check failed! Resetting password to 'admin123'.")
                admin_user.set_password('admin123')
                updated = True
                logging.debug(f"Admin password reset. New hash: {admin_user.password_hash}")

            if updated:
                 try:
                     db.session.commit()
                     logging.info(f"Admin user updates committed successfully.")
                 except Exception as commit_error:
                     db.session.rollback()
                     logging.error(f"ERROR committing admin user updates: {commit_error}")
            else:
                 logging.debug(f"Admin user '{admin_email}' already exists and is up-to-date (or password check passed).")

        # --- Ensure Base Achievements Exist ---
        ensure_achievements_exist()

    except Exception as e:
        logging.error(f"An error occurred during database initialization/migration: {e}")
        db.session.rollback()

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

# Serve static files - Adjusted to potentially serve uploads
@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

# Add context processor for footer year
import datetime
@app.context_processor
def inject_now():
    return {'now': datetime.datetime.utcnow}

# --- Database Connection Check (Optional but good practice) ---
with app.app_context():
    try:
        db.session.execute(text("SELECT 1"))
        logging.info("✅ Database connection successful.")
    except Exception as e:
        logging.error(f"❌ Database connection failed: {e}")

# --- Run the App ---
if __name__ == '__main__':
    host = os.getenv('FLASK_RUN_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_RUN_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() in ['true', '1', 't']
    app.run(host=host, port=port, debug=debug)

