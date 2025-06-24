# src/models/user.py

# -*- coding: utf-8 -*-
import datetime
from datetime import datetime, date
# REMOVIDO: A importação do SQLAlchemy foi movida para extensions.py
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

# ALTERADO: Importa a instância 'db' do arquivo central de extensões.
from src.extensions import db

try:
    from .law import Law 
    # =====================================================================
    # <<< INÍCIO DA IMPLEMENTAÇÃO 1/3: IMPORTAR O MODELO 'Concurso' >>>
    # =====================================================================
    # Importação do modelo Concurso para criar o relacionamento.
    from .concurso import Concurso
    # =====================================================================
    # <<< FIM DA IMPLEMENTAÇÃO 1/3 >>>
    # =====================================================================
except ImportError:
    pass 

# REMOVIDO: A linha 'db = SQLAlchemy()' foi movida para o arquivo extensions.py
# e agora é importada acima.

# Association table for User-Achievement relationship
achievements_association = db.Table("user_achievements",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("achievement_id", db.Integer, db.ForeignKey("achievement.id"), primary_key=True)
)

# Tabela de Associação User-Favorite Law
favorites_association = db.Table("user_favorites",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
    db.Column("law_id", db.Integer, db.ForeignKey("law.id", ondelete="CASCADE"), primary_key=True)
)

# =====================================================================
# <<< INÍCIO DA IMPLEMENTAÇÃO 2/3: NOVA TABELA DE ASSOCIAÇÃO USER-CONCURSO >>>
# =====================================================================
# Esta tabela conecta os usuários aos concursos.
user_concurso_association = db.Table('user_concurso_association',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id', ondelete="CASCADE"), primary_key=True),
    db.Column('concurso_id', db.Integer, db.ForeignKey('concurso.id', ondelete="CASCADE"), primary_key=True)
)
# =====================================================================
# <<< FIM DA IMPLEMENTAÇÃO 2/3 >>>
# =====================================================================


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False) # Changed from username to email
    full_name = db.Column(db.String(120), nullable=True) # Added full name
    phone = db.Column(db.String(20), nullable=True) # Added phone number
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(10), nullable=False, default="student") # "admin" or "student"
    is_approved = db.Column(db.Boolean, nullable=False, default=False)
    points = db.Column(db.Integer, default=0, nullable=False) # Added points field
    favorite_label = db.Column(db.String(100), nullable=True)
    default_concurso_id = db.Column(db.Integer, db.ForeignKey('concurso.id'), nullable=True)

    # =====================================================================
    # <<< INÍCIO DA NOVA IMPLEMENTAÇÃO: CAMPOS DE DATA E HORA >>>
    # Adicionamos os campos para registrar a data de criação e o último acesso do usuário.
    # - created_at: Registra a data e hora no momento em que o usuário é criado.
    # - last_seen: Atualiza automaticamente sempre que o registro do usuário for alterado.
    # =====================================================================
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    # =====================================================================
    # <<< FIM DA NOVA IMPLEMENTAÇÃO >>>
    # =====================================================================

    # =====================================================================
    # <<< INÍCIO DA IMPLEMENTAÇÃO 3/3: NOVOS CAMPOS E RELACIONAMENTOS >>>
    # =====================================================================
    # Coluna de controle, com a correção 'server_default' para evitar erros de migração.
    can_see_all_concursos = db.Column(db.Boolean, nullable=False, server_default='true')

    # Relacionamento muitos-para-muitos com o modelo Concurso
    associated_concursos = db.relationship(
        'Concurso',
        secondary=user_concurso_association,
        backref=db.backref('associated_users', lazy='dynamic'),
        lazy='dynamic'
    )
    # =====================================================================
    # <<< FIM DA IMPLEMENTAÇÃO 3/3 >>>
    # =====================================================================

    # Relationships
    progress = db.relationship("UserProgress", backref="user", lazy=True)
    achievements = db.relationship("Achievement", secondary=achievements_association, lazy="subquery",
                                 backref=db.backref("users", lazy=True))
    
    favorite_laws = db.relationship("Law", secondary=favorites_association, lazy="dynamic", 
                                  backref=db.backref("favorited_by_users", lazy=True))
    
    study_activities = db.relationship("StudyActivity", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    todo_items = db.relationship("TodoItem", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if self.password_hash is None:
            return False
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email}>"

    @property
    def username(self):
        return self.email.split("@")[0] if self.email else "User"


class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    icon = db.Column(db.String(50), nullable=True)
    points_threshold = db.Column(db.Integer, nullable=True)
    laws_completed_threshold = db.Column(db.Integer, nullable=True)

    def __repr__(self):
        return f"<Achievement {self.name}>"


class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_fixed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Announcement {self.title}>"


class UserSeenAnnouncement(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True)
    announcement_id = db.Column(db.Integer, db.ForeignKey('announcement.id', ondelete='CASCADE'), primary_key=True)
    seen_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('seen_announcements', lazy='dynamic'))
    announcement = db.relationship('Announcement', backref=db.backref('seen_by_users', lazy='dynamic'))

    def __repr__(self):
        return f'<UserSeenAnnouncement user={self.user_id} announcement={self.announcement_id}>'


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


class TodoItem(db.Model):
    """
    Represents um item de tarefa no diário pessoal do usuário.
    """
    __tablename__ = 'todo_item'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    
    law_id = db.Column(db.Integer, db.ForeignKey('law.id', ondelete='SET NULL'), nullable=True)
    law = db.relationship('Law', backref='todo_items')

    content = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(50), nullable=False, default='lembrete')
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<TodoItem {self.id} (User: {self.user_id}): {self.content[:30]}...>"
