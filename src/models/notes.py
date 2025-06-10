# src/models/notes.py

# -*- coding: utf-8 -*-
from src.models.user import db
import datetime

class UserNotes(db.Model):
    __tablename__ = 'user_notes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    law_id = db.Column(db.Integer, db.ForeignKey("law.id", ondelete="CASCADE"), nullable=False)
    content = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = db.relationship("User", backref=db.backref("notes", lazy=True, cascade="all, delete-orphan"))
    law = db.relationship("Law", backref=db.backref("law_notes", lazy=True, cascade="all, delete-orphan"))

    __table_args__ = (db.UniqueConstraint("user_id", "law_id", name="_user_law_notes_uc"),)

    def __repr__(self):
        return f"<UserNotes User: {self.user_id} Law: {self.law_id}>"


# =====================================================================
# <<< INÍCIO: MODELO OTIMIZADO PARA MARCAÇÕES DE TEXTO >>>
# O modelo UserLawMarkup foi completamente substituído para seguir a
# abordagem de salvar apenas os "diffs" (offsets) em vez do HTML completo.
# =====================================================================
class UserLawMarkup(db.Model):
    __tablename__ = 'user_law_markups'  # Tabela renomeada para o plural

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    law_id = db.Column(db.Integer, db.ForeignKey("law.id", ondelete="CASCADE"), nullable=False)

    # Tipo de marcação: 'highlight' ou 'bold'
    markup_type = db.Column(db.String(20), nullable=False)

    # Posição do caractere inicial e final da marcação, relativo ao texto puro.
    start_offset = db.Column(db.Integer, nullable=False)
    end_offset = db.Column(db.Integer, nullable=False)

    # O texto selecionado, para validação e referência.
    selected_text = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    # Removido o UniqueConstraint de user_id e law_id, pois agora um usuário
    # pode ter múltiplas marcações para a mesma lei.
    # Adicionado um índice para otimizar as consultas.
    __table_args__ = (db.Index('idx_user_law_markup', 'user_id', 'law_id'),)


    def __repr__(self):
        return f"<UserLawMarkup User: {self.user_id} Law: {self.law_id} Type: {self.markup_type}>"

    def to_dict(self):
        """Converte o objeto em um dicionário para serialização JSON."""
        return {
            "type": self.markup_type,
            "start": self.start_offset,
            "end": self.end_offset,
            "text": self.selected_text
        }
# =====================================================================
# <<< FIM: MODELO OTIMIZADO >>>
# =====================================================================
