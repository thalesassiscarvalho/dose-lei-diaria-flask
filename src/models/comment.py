# src/models/comment.py
# CÓDIGO COMPLETO E ATUALIZADO

from src.extensions import db
import datetime
# =====================================================================
# <<< INÍCIO DA ALTERAÇÃO: IMPORTAR Index >>>
# =====================================================================
from sqlalchemy import Index
# =====================================================================
# <<< FIM DA ALTERAÇÃO >>>
# =====================================================================

class UserComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    
    # Adicionamos index=True para acelerar a busca de todos os comentários de um usuário
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    # E aqui para buscar todos os comentários de uma lei
    law_id = db.Column(db.Integer, db.ForeignKey("law.id", ondelete="CASCADE"), nullable=False, index=True)
    anchor_paragraph_id = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    user = db.relationship("User", backref="comments")
    law = db.relationship("Law", backref=db.backref("comments", cascade="all, delete-orphan"))

    # =====================================================================
    # <<< INÍCIO DA ALTERAÇÃO: ÍNDICE COMPOSTO >>>
    # =====================================================================
    # Otimiza a query principal: "buscar todos os comentários de um usuário específico
    # para uma lei específica".
    __table_args__ = (
        Index('ix_user_comment_user_id_law_id', 'user_id', 'law_id'),
    )
    # =====================================================================
    # <<< FIM DA ALTERAÇÃO >>>
    # =====================================================================

    def __repr__(self):
        return f"<UserComment {self.id} User: {self.user_id}>"
