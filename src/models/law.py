# -*- coding: utf-8 -*-
from src.models.user import db 
from sqlalchemy.orm import backref

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    # MODIFICADO: Alterado o backref para não conflitar com a nova relação em Law
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

    # =====================================================================
    # <<< INÍCIO: CAMPOS PARA A NOVA ESTRUTURA HIERÁRQUICA >>>
    # =====================================================================
    
    # Campo que armazena o ID do pai. Se for nulo, é um item principal (Diploma).
    parent_id = db.Column(db.Integer, db.ForeignKey('law.id'), nullable=True)

    # Relação para acessar os filhos de um item principal (Diploma).
    # A cascata garante que, se um Diploma for deletado, todos os seus Tópicos filhos também serão.
    children = db.relationship('Law', 
                               backref=backref('parent', remote_side=[id]), 
                               lazy='dynamic', 
                               cascade="all, delete-orphan")
    
    # =====================================================================
    # <<< FIM: CAMPOS PARA A NOVA ESTRUTURA HIERÁRQUICA >>>
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
