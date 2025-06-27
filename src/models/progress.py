# src/models/progress.py
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

class UserProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    law_id = db.Column(db.Integer, db.ForeignKey("law.id", ondelete="CASCADE"), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    last_read_article = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='nao_iniciado', server_default='nao_iniciado')
    
    # =====================================================================
    # <<< INÍCIO DA ALTERAÇÃO: ADICIONANDO ÍNDICE NO CAMPO >>>
    # =====================================================================
    # Adicionamos um índice neste campo, pois a busca de atividades recentes
    # ordena os resultados por ele. Isso tornará a ordenação muito mais rápida.
    last_accessed_at = db.Column(db.DateTime, nullable=True, default=datetime.datetime.utcnow, index=True) 
    # =====================================================================
    # <<< FIM DA ALTERAÇÃO >>>
    # =====================================================================

    law = db.relationship("Law", backref=db.backref("progress_records", cascade="all, delete-orphan"))

    # A UniqueConstraint abaixo já cria um índice na combinação (user_id, law_id),
    # o que é ótimo para buscas por um progresso específico.
    __table_args__ = (
        db.UniqueConstraint("user_id", "law_id", name="_user_law_uc"),
        # =====================================================================
        # <<< INÍCIO DA ALTERAÇÃO: ÍNDICE COMPOSTO ADICIONAL >>>
        # =====================================================================
        # Este novo índice composto é o "pulo do gato" para a feature de "Atividades Recentes".
        # Ele otimiza a consulta que busca os progressos de um usuário específico,
        # já ordenados pela data de último acesso.
        Index('ix_userprogress_user_id_last_accessed_at', 'user_id', 'last_accessed_at'),
        # =====================================================================
        # <<< FIM DA ALTERAÇÃO >>>
        # =====================================================================
    )

    def __repr__(self):
        return f"<UserProgress User: {self.user_id} Law: {self.law_id} Status: {self.status}>"
