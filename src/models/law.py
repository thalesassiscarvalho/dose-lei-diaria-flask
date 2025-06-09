# -*- coding: utf-8 -*-
from src.models.user import db # Import db from a central place if possible

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    laws = db.relationship("Law", backref="subject", lazy=True)

    def __repr__(self):
        return f"<Subject {self.name}>"

class Law(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    content = db.Column(db.Text, nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=True)
    audio_url = db.Column(db.String(500), nullable=True)

    # NOVO: Relacionamento com Links Úteis
    # A cascata garante que, se uma lei for deletada, seus links também serão.
    useful_links = db.relationship('UsefulLink', back_populates='law', lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        audio_indicator = " (Audio)" if self.audio_url else ""
        return f"<Law {self.title}{audio_indicator}>"

# --- NOVO MODELO PARA LINKS ÚTEIS ---
class UsefulLink(db.Model):
    __tablename__ = 'useful_link' # Nome explícito para a tabela
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    
    # Chave estrangeira para conectar o link à lei
    law_id = db.Column(db.Integer, db.ForeignKey('law.id'), nullable=False)
    
    # Relação de volta para a Lei
    law = db.relationship('Law', back_populates='useful_links')

    def __repr__(self):
        return f'<UsefulLink {self.title}>'
