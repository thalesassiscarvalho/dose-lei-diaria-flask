# -*- coding: utf-8 -*-
from src.models.user import db
import datetime

class UserNotes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # MODIFICADO: Adicionado ondelete="CASCADE"
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    law_id = db.Column(db.Integer, db.ForeignKey("law.id", ondelete="CASCADE"), nullable=False)
    content = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = db.relationship("User", backref=db.backref("notes", lazy=True, cascade="all, delete-orphan"))
    # MODIFICADO: Adicionado cascade="all, delete-orphan"
    law = db.relationship("Law", backref=db.backref("law_notes", lazy=True, cascade="all, delete-orphan"))

    __table_args__ = (db.UniqueConstraint("user_id", "law_id", name="_user_law_notes_uc"),)

    def __repr__(self):
        return f"<UserNotes User: {self.user_id} Law: {self.law_id}>"


# =====================================================================
# <<< INÍCIO: NOVA CLASSE PARA MARCAÇÕES DE TEXTO DA LEI >>>
# Adicione esta classe completa ao final do seu arquivo.
# =====================================================================


# ------------------------------------------------------------------
# Nova versão enxuta: armazena apenas o DIFF da marcação
# ------------------------------------------------------------------
class UserLawMarkup(db.Model):
    """Cada registro representa um trecho marcado pelo usuário
    (negrito ou destaque) armazenado como offsets, não HTML.
    """
    __tablename__ = "user_law_markup"

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    law_id       = db.Column(db.Integer, db.ForeignKey("law.id",  ondelete="CASCADE"), nullable=False)

    type         = db.Column(db.String(20), nullable=False)     # 'bold' | 'highlight'
    start_offset = db.Column(db.Integer,       nullable=False)  # início (unicode‑aware)
    end_offset   = db.Column(db.Integer,       nullable=False)  # fim exclusivo

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = db.relationship("User", backref=db.backref("law_markups", lazy=True, cascade="all, delete-orphan"))
    law  = db.relationship("Law",  backref=db.backref("user_markups", lazy=True, cascade="all, delete-orphan"))

    __table_args__ = (
        db.UniqueConstraint("user_id", "law_id", "start_offset", "end_offset", "type", name="_user_law_markup_uc"),
        db.Index("idx_markup_lookup", "user_id", "law_id")
    )

    def __repr__(self):
        return f"<UserLawMarkup User: {self.user_id} Law: {self.law_id} type {self.type} offsets ({self.start_offset},{self.end_offset})>"

