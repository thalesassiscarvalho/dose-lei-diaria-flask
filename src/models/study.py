# src/models/study.py
# CÓDIGO COMPLETO E ATUALIZADO

from src.extensions import db
from datetime import datetime
from sqlalchemy import Index # IMPORTAR Index

class StudySession(db.Model):
    __tablename__ = 'study_sessions'

    id = db.Column(db.Integer, primary_key=True)
    # =====================================================================
    # <<< INÍCIO DA ALTERAÇÃO 1/2: ADICIONANDO ÍNDICES >>>
    # =====================================================================
    # Adicionar index=True acelera as buscas que filtram por user_id.
    # Ex: "SELECT * FROM study_sessions WHERE user_id = ?;"
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    law_id = db.Column(db.Integer, db.ForeignKey('law.id'), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False, index=True)
    # =====================================================================
    # <<< FIM DA ALTERAÇÃO 1/2 >>>
    # =====================================================================

    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=False, default=0)
    entry_type = db.Column(db.String(10), nullable=False, default='auto')
    recorded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship('User', backref='study_sessions')
    law = db.relationship('Law', backref='study_sessions')
    subject = db.relationship('Subject', backref='study_sessions_by_subject')

    # =====================================================================
    # <<< INÍCIO DA ALTERAÇÃO 2/2: ÍNDICE COMPOSTO >>>
    # =====================================================================
    # __table_args__ permite definir configurações avançadas para a tabela.
    # Aqui, estamos criando um índice composto. Isso é extremamente útil para
    # queries que filtram por usuário E data ao mesmo tempo, como nos cálculos
    # de estatísticas (ex: "tempo estudado na última semana").
    __table_args__ = (
        Index('ix_study_sessions_user_id_recorded_at', 'user_id', 'recorded_at'),
    )
    # =====================================================================
    # <<< FIM DA ALTERAÇÃO 2/2 >>>
    # =====================================================================

    def __repr__(self):
        return f"<StudySession {self.id} | User: {self.user_id} | Law: {self.law_id} | Duration: {self.duration_seconds}s>"
