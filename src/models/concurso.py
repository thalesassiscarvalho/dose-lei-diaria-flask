# src/models/concurso.py
from src.models.user import db
from sqlalchemy.orm import backref

# Tabela de Associação Muitos-para-Muitos
# Esta tabela especial não precisa de uma classe Model, pois ela apenas armazena
# os IDs que conectam um Concurso a uma Lei.
concurso_law_association = db.Table('concurso_law_association',
    db.Column('concurso_id', db.Integer, db.ForeignKey('concurso.id', ondelete="CASCADE"), primary_key=True),
    db.Column('law_id', db.Integer, db.ForeignKey('law.id', ondelete="CASCADE"), primary_key=True)
)

class Concurso(db.Model):
    """
    Representa um concurso público específico, como 'TJSP - Escrevente 2025'.
    """
    __tablename__ = 'concurso'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    
    # =====================================================================
    # <<< INÍCIO DA IMPLEMENTAÇÃO: CAMPO PARA EDITAL VERTICALIZADO >>>
    # =====================================================================
    edital_verticalizado_url = db.Column(db.String(300), nullable=True)
    # =====================================================================
    # <<< FIM DA IMPLEMENTAÇÃO >>>
    # =====================================================================

    # Relação Muitos-para-Muitos com a tabela Law
    # 'secondary' aponta para a nossa tabela de associação.
    # 'back_populates' cria a relação inversa no modelo Law.
    laws = db.relationship(
        'Law', 
        secondary=concurso_law_association,
        back_populates='concursos',
        lazy='dynamic' # Permite fazer queries mais complexas depois
    )

    def __repr__(self):
        return f'<Concurso {self.name}>'
