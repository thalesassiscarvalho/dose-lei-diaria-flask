# src/models/product.py
from src.extensions import db
import datetime

class Product(db.Model):
    """
    Representa um produto ou plano vendável, como um curso ou assinatura.
    """
    __tablename__ = 'product'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # É uma boa prática armazenar preços como um inteiro na menor unidade da moeda
    # para evitar erros de arredondamento. Ex: R$ 99,90 será armazenado como 9990 (centavos).
    price_cents = db.Column(db.Integer, nullable=False)

    # IDs do Stripe para conectar nosso produto com a plataforma de pagamento.
    # Vamos preencher isso mais tarde, depois de criar o produto no painel da Stripe.
    stripe_product_id = db.Column(db.String(100), unique=True, nullable=True)
    stripe_price_id = db.Column(db.String(100), unique=True, nullable=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f'<Product {self.id}: {self.name}>'