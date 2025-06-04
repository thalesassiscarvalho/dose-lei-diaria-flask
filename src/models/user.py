# -*- coding: utf-8 -*-
import datetime
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
# --- NOVO: Importar Law para a definição da tabela ---
# Assumindo que law.py está no mesmo diretório ou o import relativo funciona
# Se law.py estiver em src/models/law.py, o import pode precisar ser ajustado
# dependendo de como os modelos são inicializados/importados no seu __init__.py
# Se der erro de import, pode ser necessário remover este import e 
# usar db.ForeignKey("law.id") diretamente com aspas.
try:
    from .law import Law 
except ImportError:
    # Fallback se o import direto não funcionar (comum em algumas estruturas Flask)
    pass 
# --- FIM NOVO ---

db = SQLAlchemy()

# Association table for User-Achievement relationship
achievements_association = db.Table("user_achievements",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("achievement_id", db.Integer, db.ForeignKey("achievement.id"), primary_key=True)
)

# --- NOVO: Tabela de Associação User-Favorite Law ---
favorites_association = db.Table("user_favorites",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True), # Adicionado ondelete
    db.Column("law_id", db.Integer, db.ForeignKey("law.id", ondelete="CASCADE"), primary_key=True)    # Adicionado ondelete
)
# --- FIM NOVO ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False) # Changed from username to email
    full_name = db.Column(db.String(120), nullable=True) # Added full name
    phone = db.Column(db.String(20), nullable=True) # Added phone number
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(10), nullable=False, default="student") # "admin" or "student"
    is_approved = db.Column(db.Boolean, nullable=False, default=False)
    points = db.Column(db.Integer, default=0, nullable=False) # Added points field

    # Relationships
    progress = db.relationship("UserProgress", backref="user", lazy=True)
    achievements = db.relationship("Achievement", secondary=achievements_association, lazy="subquery",
                                 backref=db.backref("users", lazy=True))
    
    # --- NOVO: Relacionamento com Leis Favoritas ---
    favorite_laws = db.relationship("Law", secondary=favorites_association, lazy="dynamic", # Usar lazy=\'dynamic\' pode ser útil para contagens
                                  backref=db.backref("favorited_by_users", lazy=True))
    # --- FIM NOVO ---

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        # Ensure password_hash is not None before checking
        if self.password_hash is None:
            return False
        return check_password_hash(self.password_hash, password)

    # Update __repr__ to use email
    def __repr__(self):
        return f"<User {self.email}>"

    # Add a property to mimic username if needed elsewhere, though ideally update those usages
    @property
    def username(self):
        # For compatibility if username is used in templates like base.html
        # Returns the part of the email before the @ symbol
        return self.email.split("@")[0] if self.email else "User"


class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    icon = db.Column(db.String(50), nullable=True) # e.g., Font Awesome class like "fas fa-star"
    points_threshold = db.Column(db.Integer, nullable=True) # Points needed to unlock
    laws_completed_threshold = db.Column(db.Integer, nullable=True) # Laws needed to unlock
    # Add other criteria if needed (e.g., specific laws completed)

    def __repr__(self):
        return f"<Achievement {self.name}>"


class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Announcement {self.title}>"

