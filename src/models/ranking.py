# src/models/ranking.py

from .user import db, User
from sqlalchemy.orm import relationship

class UserWeeklyRanking(db.Model):
    """
    Esta tabela armazena o ranking semanal pré-calculado dos usuários
    para evitar consultas pesadas no dashboard.
    Ela deve ser atualizada por uma tarefa agendada (cron job).
    """
    __tablename__ = 'user_weekly_ranking'

    id = db.Column(db.Integer, primary_key=True)
    
    # Chave estrangeira para o usuário
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Data de início da semana para a qual o ranking se refere
    week_start_date = db.Column(db.Date, nullable=False, index=True)
    
    # Total de segundos que o usuário estudou na semana
    total_seconds = db.Column(db.Integer, nullable=False, default=0)
    
    # A faixa de percentil calculada (ex: 10, 20, 30, 50, 100)
    percentile_rank = db.Column(db.Integer, nullable=True)

    # Relacionamento para acessar o objeto User a partir de um ranking
    user = relationship('User', backref=db.backref('weekly_rankings', lazy='dynamic'))

    # Garante que não haja mais de uma entrada para o mesmo usuário na mesma semana
    __table_args__ = (db.UniqueConstraint('user_id', 'week_start_date', name='uq_user_week'),)

    def __repr__(self):
        return f'<UserWeeklyRanking UserID={self.user_id} Week={self.week_start_date} Percentile={self.percentile_rank}%>'