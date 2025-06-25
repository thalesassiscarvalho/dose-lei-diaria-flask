# -*- coding: utf-8 -*-
from src.extensions import db
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
class UserLawMarkup(db.Model):
    __tablename__ = 'user_law_markup'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    law_id = db.Column(db.Integer, db.ForeignKey("law.id", ondelete="CASCADE"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    content_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = db.relationship("User", backref=db.backref("law_markups", lazy=True, cascade="all, delete-orphan"))
    law = db.relationship("Law", backref=db.backref("user_markups", lazy=True, cascade="all, delete-orphan"))

    __table_args__ = (db.UniqueConstraint("user_id", "law_id", name="_user_law_markup_uc"),)

    def __repr__(self):
        return f"<UserLawMarkup User: {self.user_id} Law: {self.law_id}>"
# =====================================================================
# <<< FIM: NOVA CLASSE >>>
# =====================================================================
