from src.extensions import db
from datetime import datetime

class StudySession(db.Model):
    __tablename__ = 'study_sessions' # Nome da tabela no banco de dados

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Chave estrangeira para o usuário
    law_id = db.Column(db.Integer, db.ForeignKey('law.id'), nullable=False)   # Chave estrangeira para a lei estudada
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False) # Chave estrangeira para a matéria (para facilitar a agregação)

    start_time = db.Column(db.DateTime, nullable=True) # Hora de início da sessão (para cronômetro)
    end_time = db.Column(db.DateTime, nullable=True)   # Hora de fim da sessão (para cronômetro)
    duration_seconds = db.Column(db.Integer, nullable=False, default=0) # Duração em segundos

    entry_type = db.Column(db.String(10), nullable=False, default='auto') # 'auto' ou 'manual'
    recorded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow) # Quando o registro foi feito/salvo

    # Relações (opcional, mas boa prática para facilitar consultas)
    user = db.relationship('User', backref='study_sessions')
    law = db.relationship('Law', backref='study_sessions')
    subject = db.relationship('Subject', backref='study_sessions_by_subject') # 'subjects' é a tabela da matéria

    def __repr__(self):
        return f"<StudySession {self.id} | User: {self.user_id} | Law: {self.law_id} | Duration: {self.duration_seconds}s>"
