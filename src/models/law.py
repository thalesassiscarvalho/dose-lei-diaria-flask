# -*- coding: utf-8 -*-
from src.models.user import db 
from sqlalchemy.orm import backref
import datetime # Adicionado para os novos campos de data e hora

# =====================================================================
# <<< INÍCIO DA ATUALIZAÇÃO (ETAPA 1) >>>
# Novo modelo para rastrear quem viu o aviso de atualização de uma lei
# =====================================================================
class UserSeenLawNotice(db.Model):
    __tablename__ = 'user_seen_law_notice'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    law_id = db.Column(db.Integer, db.ForeignKey('law.id'), nullable=False)
    # Armazena a data da última atualização da lei que o usuário viu.
    seen_update_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'law_id'),)
# =====================================================================
# <<< FIM DA ATUALIZAÇÃO >>>
# =====================================================================


class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    laws = db.relationship("Law", backref="subject", lazy=True, foreign_keys='Law.subject_id')

    def __repr__(self):
        return f"<Subject {self.name}>"

class Law(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    content = db.Column(db.Text, nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=True)
    audio_url = db.Column(db.String(500), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('law.id'), nullable=True)

    # =====================================================================
    # <<< INÍCIO DA ATUALIZAÇÃO (ETAPA 1) >>>
    # Novos campos para rastrear e descrever as atualizações.
    # =====================================================================
    last_updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    active_update_notice = db.Column(db.Text, nullable=True) # Campo para o seu aviso
    # =====================================================================
    # <<< FIM DA ATUALIZAÇÃO >>>
    # =====================================================================

    # =====================================================================
    # <<< INÍCIO DA CORREÇÃO DEFINITIVA >>>
    # O parâmetro 'lazy="dynamic"' foi REMOVIDO da relação abaixo.
    # Esta é a principal correção que resolve o conflito.
    # =====================================================================
    children = db.relationship('Law', 
                               backref=backref('parent', remote_side=[id]),
                               cascade="all, delete-orphan")
    # =====================================================================
    # <<< FIM DA CORREÇÃO DEFINITIVA >>>
    # =====================================================================

    useful_links = db.relationship('UsefulLink', back_populates='law', lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        audio_indicator = " (Audio)" if self.audio_url else ""
        return f"<Law {self.title}{audio_indicator}>"

class UsefulLink(db.Model):
    __tablename__ = 'useful_link'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    law_id = db.Column(db.Integer, db.ForeignKey('law.id'), nullable=False)
    law = db.relationship('Law', back_populates='useful_links')

    def __repr__(self):
        return f'<UsefulLink {self.title}>'
