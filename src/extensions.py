# -*- coding: utf-8 -*-
"""
Arquivo central para inicialização das extensões Flask.
Isso evita importações circulares, seguindo o padrão Application Factory.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager

# Instancia as extensões
db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
login_manager = LoginManager()

# Configura o login_manager
login_manager.login_view = 'auth.login'