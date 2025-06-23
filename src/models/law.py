# -*- coding: utf-8 -*-
# NOVO: Importa a tabela de associação do arquivo concurso.py
from src.models.concurso import concurso_law_association
from src.extensions import db
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

    # --- FUNCIONALIDADE EXISTENTE: Explicação do Juridiquês ---
    juridiques_explanation = db.Column(db.Text, nullable=True)

    # --- FUNCIONALIDADE EXISTENTE: Relação com Tópicos Filhos (children) ---
    children = db.relationship('Law', 
                               backref=backref('parent', remote_side=[id]),
                               cascade="all, delete-orphan")

    # --- FUNCIONALIDADE EXISTENTE: Relação com Links Úteis ---
    useful_links = db.relationship('UsefulLink', back_populates='law', lazy="dynamic", cascade="all, delete-orphan")

    # --- FUNCIONALIDADE EXISTENTE: Relação com Banner ---
    # Esta é a relação com o banner que você mencionou. Ela está mantida aqui.
    banner = db.relationship('LawBanner', backref='law', uselist=False, cascade="all, delete-orphan")
    
    # =====================================================================
    # <<< INÍCIO DA NOVA IMPLEMENTAÇÃO: Relação com Concursos >>>
    # Esta é a única seção nova, que conecta a Lei aos Concursos.
    # =====================================================================
    concursos = db.relationship(
        'Concurso',
        secondary=concurso_law_association,
        back_populates='laws'
    )
    # =====================================================================
    # <<< FIM DA NOVA IMPLEMENTAÇÃO >>>
    # =====================================================================


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
