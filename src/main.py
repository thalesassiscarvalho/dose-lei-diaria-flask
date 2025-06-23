# src/main.py

# -*- coding: utf-8 -*-
import os
import sys
import logging
import datetime
from flask import Flask, redirect, url_for, flash, send_from_directory, render_template
from flask_login import current_user
from dotenv import load_dotenv
from sqlalchemy import text

# Importa as instâncias do nosso novo arquivo central de extensões.
from .extensions import db, mail, login_manager, migrate, csrf

# Importa os modelos e os blueprints
from .models.user import User, Achievement
from .routes.auth import auth_bp
from .routes.admin import admin_bp
from .routes.student import student_bp

def create_app():
    """
    Cria e configura uma instância da aplicação Flask.
    Este é o padrão "Application Factory".
    """
    
    # Carrega as variáveis de ambiente do arquivo .env
    load_dotenv()
    logging.basicConfig(level=logging.DEBUG)

    # Cria a aplicação Flask
    app = Flask(__name__,
                static_folder='static',
                template_folder='templates')

    # Carrega a configuração a partir das variáveis de ambiente
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Recomendado adicionar
    app.config['SECURITY_PASSWORD_SALT'] = os.environ.get('SECURITY_PASSWORD_SALT')
    
    # Configuração de E-mail
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't']
    app.config['MAIL_USERNAME'] = os.environ.get('EMAIL_USER')
    app.config['MAIL_PASSWORD'] = os.environ.get('EMAIL_PASS')
    
    # Política de Segurança de Conteúdo (CSP)
    app.config['CSP_POLICY'] = {
        'default-src': ["'self'"],
        'script-src': ["'self'", "'unsafe-inline'", 'https://cdn.jsdelivr.net', 'https://cdn.tailwindcss.com', 'https://cdn.quilljs.com', 'https://cdn.tiny.cloud', 'https://kit.fontawesome.com'],
        'style-src': ["'self'", "'unsafe-inline'", 'https://cdn.jsdelivr.net', 'https://cdnjs.cloudflare.com', 'https://cdn.quilljs.com', 'https://cdn.tiny.cloud', 'https://fonts.googleapis.com', 'https://ka-f.fontawesome.com'],
        'font-src': ["'self'", 'https://cdnjs.cloudflare.com', 'https://fonts.gstatic.com', 'https://ka-f.fontawesome.com'],
        'img-src': ["'self'", 'data:', 'https://cdn.tiny.cloud'],
        'media-src': ["'self'", 'https://audios-estudoleieca.s3.us-west-2.amazonaws.com'],
        'connect-src': ["'self'", 'https://cdn.tiny.cloud', 'https://ka-f.fontawesome.com', 'https://cdn.jsdelivr.net', 'https://cdnjs.cloudflare.com', 'https://cdn.quilljs.com', 'https://audios-estudoleieca.s3.us-west-2.amazonaws.com'],
        'frame-ancestors': ["'none'"], 'object-src': ["'none'"], 'form-action': ["'self'"], 'base-uri': ["'self'"]
    }
    
    # Inicializa as extensões com a app, quebrando o ciclo de importação
    db.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Registra os Blueprints (as coleções de rotas)
    app.register_blueprint(auth_bp, url_prefix='/')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(student_bp, url_prefix='/student')

    # Registra as rotas e funções de contexto
    register_routes_and_processors(app)
    
    # Comandos de inicialização que precisam do contexto da aplicação
    with app.app_context():
        # db.create_all() # O Flask-Migrate gerencia a criação de tabelas
        ensure_achievements_exist(app)
        ensure_admin_user_exists(app)
        check_db_connection(app)

    return app


# Funções de registro para manter 'create_app' limpa
def register_routes_and_processors(app):
    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

    @app.after_request
    def apply_csp(response):
        policy = app.config.get('CSP_POLICY', {})
        csp_header_value = "; ".join([f"{key} {' '.join(values)}" for key, values in policy.items()])
        response.headers['Content-Security-Policy'] = csp_header_value
        return response
        
    @app.context_processor
    def inject_now():
        return {'now': datetime.datetime.utcnow}

# Funções de inicialização
def ensure_achievements_exist(app):
    with app.app_context():
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

def ensure_admin_user_exists(app):
    with app.app_context():
        admin_email = os.environ.get('ADMIN_EMAIL', "admin@example.com")
        admin_pass = os.environ.get('ADMIN_PASSWORD', "admin123")
        
        if not User.query.filter_by(email=admin_email).first():
            logging.info(f"Admin user not found. Creating new admin user: {admin_email}")
            admin_user = User(email=admin_email, role='admin', is_approved=True, full_name='Admin')
            admin_user.set_password(admin_pass)
            db.session.add(admin_user)
            try:
                db.session.commit()
                logging.info("Default admin user created successfully.")
            except Exception as e:
                db.session.rollback()
                logging.error(f"ERROR committing new admin user: {e}")

def check_db_connection(app):
    with app.app_context():
        try:
            db.session.execute(text("SELECT 1"))
            logging.info("✅ Conexão com o banco de dados bem-sucedida!")
        except Exception as e:
            logging.error(f"❌ Falha na conexão com o banco de dados: {e}")
