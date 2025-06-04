# -*- coding: utf-8 -*-
from .user import db # Import db from user.py or a central models init
import datetime

class UserProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    law_id = db.Column(db.Integer, db.ForeignKey("law.id"), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True) # Allow null for incomplete
    last_read_article = db.Column(db.String(50), nullable=True) # Add field for last read article
    status = db.Column(db.String(20), nullable=False, default='nao_iniciado', server_default='nao_iniciado') # NEW: nao_iniciado, em_andamento, concluido
    last_accessed_at = db.Column(db.DateTime, nullable=True, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow) # NOVO: Campo para último acesso/atualização

    # Define relationships if not already defined via backref
    law = db.relationship("Law", backref="progress_records")
    user = db.relationship("User", backref="progress_records") # Adicionado relacionamento com User para facilitar consultas

    # Unique constraint to prevent duplicate progress entries for the same user and law
    __table_args__ = (db.UniqueConstraint("user_id", "law_id", name="_user_law_uc"),)

    def __repr__(self):
        return f"<UserProgress User: {self.user_id} Law: {self.law_id} Status: {self.status} LastAccessed: {self.last_accessed_at}>" # Atualizado repr

