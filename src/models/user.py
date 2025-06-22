# -*- coding: utf-8 -*-
import datetime
from datetime import datetime, date # Adicionado 'date' para o novo modelo
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

    # =====================================================================
    # <<< INÍCIO DA IMPLEMENTAÇÃO: NOME PERSONALIZADO PARA FAVORITOS >>>
    # =====================================================================
    favorite_label = db.Column(db.String(100), nullable=True)
    # =====================================================================
    # <<< FIM DA IMPLEMENTAÇÃO >>>
    # =====================================================================
    # =====================================================================
    # <<< AQUI FOI A ÚNICA LINHA ADICIONADA >>>
    # =====================================================================
    default_concurso_id = db.Column(db.Integer, db.ForeignKey('concurso.id'), nullable=True)
    # =====================================================================

    # Relationships
    progress = db.relationship("UserProgress", backref="user", lazy=True)
    achievements = db.relationship("Achievement", secondary=achievements_association, lazy="subquery",
                                 backref=db.backref("users", lazy=True))
    
    # --- NOVO: Relacionamento com Leis Favoritas ---
    favorite_laws = db.relationship("Law", secondary=favorites_association, lazy="dynamic", # Usar lazy='dynamic' pode ser útil para contagens
                                  backref=db.backref("favorited_by_users", lazy=True))
    # --- FIM NOVO ---
    
    # =====================================================================
    # <<< INÍCIO DA IMPLEMENTAÇÃO: STREAK DE ESTUDOS >>>
    # =====================================================================
    study_activities = db.relationship("StudyActivity", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    # =====================================================================
    # <<< FIM DA IMPLEMENTAÇÃO: STREAK DE ESTUDOS >>>
    # =====================================================================

    # =====================================================================
    # <<< INÍCIO DA IMPLEMENTAÇÃO: NOVO RELACIONAMENTO PARA MEU DIÁRIO >>>
    # =====================================================================
    todo_items = db.relationship("TodoItem", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    # =====================================================================
    # <<< FIM DA IMPLEMENTAÇÃO: NOVO RELACIONAMENTO PARA MEU DIÁRIO >>>
    # =====================================================================

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
    is_fixed = db.Column(db.Boolean, default=False, nullable=False) # Campo para aviso fixo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Announcement {self.title}>"


# Tabela para rastrear avisos vistos por usuários
class UserSeenAnnouncement(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True)
    announcement_id = db.Column(db.Integer, db.ForeignKey('announcement.id', ondelete='CASCADE'), primary_key=True)
    seen_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('seen_announcements', lazy='dynamic'))
    announcement = db.relationship('Announcement', backref=db.backref('seen_by_users', lazy='dynamic'))

    def __repr__(self):
        return f'<UserSeenAnnouncement user={self.user_id} announcement={self.announcement_id}>'

# =====================================================================
# <<< INÍCIO DA IMPLEMENTAÇÃO: STREAK DE ESTUDOS >>>
# =====================================================================

class StudyActivity(db.Model):
    """Registra a atividade de estudo diária de um usuário para a funcionalidade de streak."""
    __tablename__ = 'study_activity'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    study_date = db.Column(db.Date, nullable=False, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Garante que só haverá um registro por usuário por dia
    __table_args__ = (db.UniqueConstraint('user_id', 'study_date', name='_user_study_date_uc'),)

    def __repr__(self):
        return f'<StudyActivity User {self.user_id} on {self.study_date}>'

# =====================================================================
# <<< FIM DA IMPLEMENTAÇÃO: STREAK DE ESTUDOS >>>
# =====================================================================


# =====================================================================
# <<< INÍCIO DA NOVA FUNCIONALIDADE: MODELOS PARA BANNERS DE LEI >>>
# =====================================================================

class LawBanner(db.Model):
    """
    Armazena o conteúdo do banner para uma lei específica.
    Cada lei pode ter no máximo um banner (relação um-para-um).
    """
    __tablename__ = 'law_banner'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Chave estrangeira para a lei, garantindo que seja única
    law_id = db.Column(db.Integer, db.ForeignKey('law.id', ondelete='CASCADE'), unique=True, nullable=False)

    def __repr__(self):
        return f'<LawBanner para Law ID {self.law_id}>'

class UserSeenLawBanner(db.Model):
    """
    Rastreia qual usuário viu qual versão específica do banner de uma lei.
    A 'versão' é identificada pelo timestamp 'last_updated' do banner.
    """
    __tablename__ = 'user_seen_law_banner'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    law_id = db.Column(db.Integer, db.ForeignKey('law.id', ondelete='CASCADE'), nullable=False)
    
    # Armazena o timestamp exato do banner que foi visto
    seen_at_timestamp = db.Column(db.DateTime, nullable=False)
    
    # Relações para facilitar consultas
    user = db.relationship('User', backref=db.backref('seen_law_banners', lazy='dynamic'))
    law = db.relationship('Law', backref=db.backref('seen_by_users', lazy='dynamic'))

    # Garante que um usuário só pode ter um registro de 'visto' para uma versão específica do banner
    __table_args__ = (db.UniqueConstraint('user_id', 'law_id', 'seen_at_timestamp', name='_user_law_timestamp_uc'),)

    def __repr__(self):
        return f'<UserSeenLawBanner user={self.user_id} law={self.law_id} @ {self.seen_at_timestamp}>'

# =====================================================================
# <<< FIM DA NOVA FUNCIONALIDADE >>>
# =====================================================================

# =====================================================================
# <<< INÍCIO DA IMPLEMENTAÇÃO: NOVA CLASSE TodoItem PARA MEU DIÁRIO >>>
# =====================================================================
class TodoItem(db.Model):
    """
    Represents um item de tarefa no diário pessoal do usuário.
    """
    __tablename__ = 'todo_item'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    content = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(50), nullable=False, default='lembrete') # <<< LINHA ADICIONADA >>>
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<TodoItem {self.id} (User: {self.user_id}): {self.content[:30]}...>"
# =====================================================================
# <<< FIM DA IMPLEMENTAÇÃO: NOVA CLASSE TodoItem PARA MEU DIÁRIO >>>
# =====================================================================
