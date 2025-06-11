# -*- coding: utf-8 -*-
import datetime
from src.models.user import db 
from sqlalchemy.orm import backref

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

    children = db.relationship('Law', 
                               backref=backref('parent', remote_side=[id]),
                               cascade="all, delete-orphan")

    useful_links = db.relationship('UsefulLink', back_populates='law', lazy="dynamic", cascade="all, delete-orphan")
    
    # --- Funcionalidade: Entendendo o Juridiquês ---
    juridiques_terms = db.relationship('JuridiquesTerm', back_populates='law', lazy="dynamic", cascade="all, delete-orphan")
    
    # --- Funcionalidade: Aviso de Atualização de Lei ---
    last_updated_at = db.Column(db.DateTime, nullable=True, comment="Data da última atualização da lei que gerou um aviso.")
    #                                                                           <<< AQUI ESTÁ A CORREÇÃO
    active_update_notice = db.Column(db.Boolean, default=False, nullable=False, server_default='false', comment="Indica se há um aviso de atualização ativo para esta lei.")


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

class JuridiquesTerm(db.Model):
    __tablename__ = 'juridiques_term'
    id = db.Column(db.Integer, primary_key=True)
    term = db.Column(db.String(200), nullable=False)
    definition = db.Column(db.Text, nullable=False)
    law_id = db.Column(db.Integer, db.ForeignKey('law.id'), nullable=False)
    law = db.relationship('Law', back_populates='juridiques_terms')

    def __repr__(self):
        return f'<JuridiquesTerm {self.term}>'

# --- Funcionalidade: Aviso de Atualização de Lei ---
class UserSeenLawNotice(db.Model):
    __tablename__ = 'user_seen_law_notice'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    law_id = db.Column(db.Integer, db.ForeignKey('law.id'), nullable=False)
    seen_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, nullable=False)

    user = db.relationship('User')
    law = db.relationship('Law')

    __table_args__ = (db.UniqueConstraint('user_id', 'law_id', name='_user_law_notice_uc'),)

    def __repr__(self):
        return f'<UserSeenLawNotice user_id={self.user_id} law_id={self.law_id}>'
