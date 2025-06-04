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
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=True) # Allow nullable initially for existing laws
    audio_url = db.Column(db.String(500), nullable=True) # Campo para URL do áudio

    # Define relationships if not already defined via backref
    # (progress_records relationship is defined in UserProgress model via backref)

    def __repr__(self):
        # CORRIGIDO: Removido erro de sintaxe com barras invertidas
        audio_indicator = " (Audio)" if self.audio_url else ""
        return f"<Law {self.title}{audio_indicator}>"
