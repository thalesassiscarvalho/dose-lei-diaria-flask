# src/extensions.py

from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

# Crie as instâncias aqui, sem associá-las a nenhuma app ainda.
db = SQLAlchemy()
mail = Mail()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()

# Configuração do LoginManager que precisa estar aqui
login_manager.login_view = 'auth.login'
login_manager.login_message = "Por favor, faça login para acessar esta página."
login_manager.login_message_category = "info"
