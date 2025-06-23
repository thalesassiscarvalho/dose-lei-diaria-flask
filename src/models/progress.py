# -*- coding: utf-8 -*-
from src.extensions import db
import datetime

class UserProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # MODIFICADO: Adicionado ondelete="CASCADE" para consistência no nível do banco de dados
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    law_id = db.Column(db.Integer, db.ForeignKey("law.id", ondelete="CASCADE"), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    last_read_article = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='nao_iniciado', server_default='nao_iniciado')
    last_accessed_at = db.Column(db.DateTime, nullable=True, default=datetime.datetime.utcnow) 

    # MODIFICADO: Adicionado cascade="all, delete-orphan" ao backref para apagar o progresso quando a lei for deletada
    law = db.relationship("Law", backref=db.backref("progress_records", cascade="all, delete-orphan"))

    __table_args__ = (db.UniqueConstraint("user_id", "law_id", name="_user_law_uc"),)

    def __repr__(self):
        return f"<UserProgress User: {self.user_id} Law: {self.law_id} Status: {self.status}>"
