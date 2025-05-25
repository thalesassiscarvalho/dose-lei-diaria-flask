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

from dotenv import load_dotenv
load_dotenv()

# Import models and db instance
from src.models.user import db, User, Achievement # Import Achievement
from src.models.law import Law
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
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_secret_key_replace_in_prod') # Use environment variable for secret key

# --- Database Configuration ---
# Use environment variables for database credentials for security
DATABASE_URL = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
db.init_app(app)

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

# --- Database Initialization and Migration --- 
# This needs to run within the application context
with app.app_context():
    logging.info("Initializing database and running migrations...")
    try:
        # Create all tables based on models (reflects current model state)
        db.create_all()
        logging.info("Database tables ensured (created if they didn't exist).")

        inspector = inspect(db.engine)
        
        # --- User Table Migrations ---
        user_columns = inspector.get_columns('user')
        user_column_names = [c['name'] for c in user_columns]

        # Migration for 'email'
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
                            WHEN username = 'admin' THEN 'admin@example.com' 
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

        # Migration for 'username' drop
        if 'username' in user_column_names and 'email' in user_column_names:
             logging.info("Attempting to drop 'username' column from user...")
             try:
                 db.session.execute(text("ALTER TABLE user DROP COLUMN username"))
                 db.session.commit()
                 logging.info("'username' column dropped.")
             except Exception as e:
                 logging.warning(f"Warning: Error dropping 'username' column: {e}")
                 db.session.rollback()

        # Migration for 'is_approved'
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

        # Migration for 'full_name'
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

        # Migration for 'phone'
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

        # --- User Progress Table Migrations ---
        progress_columns = inspector.get_columns('user_progress')
        progress_column_names = [c['name'] for c in progress_columns]
        
        # Migration for 'last_read_article'
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
            
        # NEW: Migration for 'status' field in user_progress
        if 'status' not in progress_column_names:
            logging.info("Attempting to add 'status' column to user_progress...")
            try:
                # Add the column with a default value
                alter_sql_add_status = text("ALTER TABLE user_progress ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'nao_iniciado'")
                db.session.execute(alter_sql_add_status)
                db.session.commit()
                logging.info("'status' column added successfully to user_progress with default 'nao_iniciado'.")
                
                # Update existing rows based on completed_at and last_read_article
                logging.info("Updating existing user_progress statuses based on completed_at and last_read_article...")
                update_concluido_sql = text("UPDATE user_progress SET status = 'concluido' WHERE completed_at IS NOT NULL AND status = 'nao_iniciado'")
                update_andamento_sql = text("UPDATE user_progress SET status = 'em_andamento' WHERE completed_at IS NULL AND last_read_article IS NOT NULL AND status = 'nao_iniciado'")
                
                result_concluido = db.session.execute(update_concluido_sql)
                db.session.commit() # Commit after first update
                logging.info(f"Updated {result_concluido.rowcount} rows to 'concluido'.")
                
                result_andamento = db.session.execute(update_andamento_sql)
                db.session.commit() # Commit after second update
                logging.info(f"Updated {result_andamento.rowcount} rows to 'em_andamento'.")
                
                logging.info("Existing user_progress statuses updated.")
                
            except OperationalError as e:
                logging.error(f"Error adding or updating 'status' column in user_progress: {e}")
                db.session.rollback()
        else:
            logging.debug("'status' column already exists in user_progress.")
            # Optional: Add logic here to ensure existing statuses are valid if needed on subsequent runs

        # --- Admin User Creation/Check --- 
        admin_email = "admin@example.com"
        logging.debug(f"Checking for admin user with email: {admin_email}")
        admin_user = User.query.filter_by(email=admin_email).first()

        if not admin_user:
            logging.info(f"Admin user not found. Creating new admin user...")
            admin_user = User(email=admin_email, role='admin', is_approved=True, full_name='Admin User')
            admin_user.set_password('admin')
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
            if not admin_user.check_password('admin'):
                logging.warning(f"Admin password check failed! Resetting password to 'admin'.")
                admin_user.set_password('admin')
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

# Serve static files
@app.route('/<path:path>')
def serve_static_or_index(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404
    if os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        return "Not Found", 404

# Add context processor for footer year
import datetime
@app.context_processor
def inject_now():
    return {'now': datetime.datetime.utcnow}

with app.app_context():
    try:
        db.session.execute(text("SELECT 1"))
        logging.info("✅ Conexão com o banco de dados bem-sucedida!")
    except Exception as e:
        logging.error(f"❌ Erro ao conectar com o banco de dados: {e}")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=True)

