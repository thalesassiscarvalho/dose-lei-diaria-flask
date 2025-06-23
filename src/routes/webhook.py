# src/routes/webhook.py
from flask import Blueprint, request, abort, current_app
import stripe
import os
import logging

from src.extensions import db
from src.models.user import User

webhook_bp = Blueprint('webhook', __name__)

@webhook_bp.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """ Rota para receber eventos do Stripe e automatizar ações. """
    
    # Pega a assinatura da requisição enviada pelo Stripe
    sig_header = request.headers.get('Stripe-Signature')
    payload = request.get_data(as_text=True)
    endpoint_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')

    if not sig_header or not payload or not endpoint_secret:
        # Se algum dos dados essenciais estiver faltando, encerre
        logging.warning("Webhook do Stripe recebido sem payload ou assinatura.")
        abort(400)

    try:
        # Verifica se o evento realmente veio do Stripe
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Payload inválido
        logging.error(f"Erro no payload do Webhook: {e}")
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        # Assinatura inválida
        logging.error(f"Erro na assinatura do Webhook: {e}")
        return 'Invalid signature', 400

    # =====================================================================
    # <<< Lógica de Automação: O que fazer com o aviso do Stripe >>>
    # =====================================================================
    
    # Se o evento for "checkout.session.completed", significa que um pagamento foi feito com sucesso
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_email = session.get('customer_details', {}).get('email')

        if customer_email:
            logging.info(f"Webhook de pagamento bem-sucedido recebido para o e-mail: {customer_email}")
            
            # Procura o usuário no nosso banco de dados com aquele e-mail
            user = User.query.filter_by(email=customer_email).first()

            if user:
                # Se encontrou o usuário, muda o status dele para aprovado
                user.is_approved = True
                db.session.commit()
                logging.info(f"Usuário {customer_email} aprovado com sucesso via Webhook.")
            else:
                # Se não encontrou, apenas registra o log.
                # No futuro, poderíamos criar o usuário aqui automaticamente.
                logging.warning(f"Pagamento recebido para o e-mail {customer_email}, mas nenhum usuário correspondente foi encontrado para aprovação.")
    
    # Responde ao Stripe com "200 OK" para confirmar que recebemos o aviso
    return 'OK', 200
