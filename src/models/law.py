# -*- coding: utf-8 -*-
from src.models.concurso import concurso_law_association
# =====================================================================
# <<< INÍCIO DA ALTERAÇÃO: IMPORTAR CommunityContribution >>>
# =====================================================================
# Precisamos que este arquivo "conheça" o modelo CommunityContribution para
# criar os relacionamentos. Usamos um 'try-except' para evitar erros circulares.
try:
    from src.models.user import CommunityContribution
except ImportError:
    pass
# =====================================================================
# <<< FIM DA ALTERAÇÃO >>>
# =====================================================================
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
    approved_contribution_id = db.Column(db.Integer, db.ForeignKey('community_contributions.id'), nullable=True)
    juridiques_explanation = db.Column(db.Text, nullable=True)

    children = db.relationship('Law', 
                               backref=backref('parent', remote_side=[id]),
                               cascade="all, delete-orphan")

    useful_links = db.relationship('UsefulLink', back_populates='law', lazy="dynamic", cascade="all, delete-orphan")
    banner = db.relationship('LawBanner', backref='law', uselist=False, cascade="all, delete-orphan")
    concursos = db.relationship(
        'Concurso',
        secondary=concurso_law_association,
        back_populates='laws'
    )

    # =====================================================================
    # <<< INÍCIO DA ALTERAÇÃO: ADICIONANDO RELACIONAMENTOS EXPLÍCITOS >>>
    # =====================================================================
    # Este relacionamento busca TODAS as contribuições que apontam para esta lei.
    # Ele usa a chave estrangeira 'CommunityContribution.law_id'.
    all_contributions = db.relationship(
        'CommunityContribution', 
        foreign_keys='CommunityContribution.law_id', 
        back_populates='law'
    )

    # Este relacionamento busca a UMA contribuição aprovada.
    # Ele usa a chave estrangeira 'Law.approved_contribution_id'.
    # 'uselist=False' diz que este é um relacionamento um-para-um (uma lei tem uma contribuição aprovada).
    approved_contribution = db.relationship(
        'CommunityContribution',
        foreign_keys=[approved_contribution_id],
        uselist=False,
        post_update=True # Ajuda a resolver o ciclo de dependência
    )
    # =====================================================================
    # <<< FIM DA ALTERAÇÃO >>>
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
