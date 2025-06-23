# src/routes/webhook.py
from flask import Blueprint, request, abort, current_app, render_template, url_for
import stripe
import os
import logging
import datetime

from src.extensions import db, csrf, mail
from src.models.user import User
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer

webhook_bp = Blueprint('webhook', __name__)

@webhook_bp.route('/stripe-webhook', methods=['POST'])
@csrf.exempt
def stripe_webhook():
    """ Rota para receber eventos do Stripe e automatizar ações. """
    
    sig_header = request.headers.get('Stripe-Signature')
    payload = request.get_data(as_text=True)
    endpoint_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')

    if not sig_header or not payload or not endpoint_secret:
        logging.warning("Webhook do Stripe recebido sem payload ou assinatura.")
        abort(400)

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        logging.error(f"Erro no payload do Webhook: {e}")
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        logging.error(f"Erro na assinatura do Webhook: {e}")
        return 'Invalid signature', 400

    # =====================================================================
    # <<< LÓGICA EXISTENTE: LIDA COM NOVAS ASSINATURAS >>>
    # =====================================================================
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_email = session.get('customer_details', {}).get('email')

        if customer_email:
            logging.info(f"Webhook de 'checkout.session.completed' recebido para: {customer_email}")
            
            user = User.query.filter_by(email=customer_email).first()

            if user:
                if not user.is_approved:
                    user.is_approved = True
                    db.session.commit()
                    logging.info(f"Usuário existente {customer_email} aprovado com sucesso via Webhook.")
                else:
                    logging.info(f"Usuário {customer_email} já estava aprovado. Nenhuma ação necessária.")
            else:
                logging.info(f"Nenhum usuário encontrado para {customer_email}. Criando nova conta...")
                
                customer_name = session.get('customer_details', {}).get('name', 'Aluno')
                
                new_user = User(
                    email=customer_email,
                    full_name=customer_name,
                    is_approved=True,
                    role='student'
                )
                db.session.add(new_user)

                serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
                token = serializer.dumps(customer_email, salt=current_app.config['SECURITY_PASSWORD_SALT'])
                set_password_url = url_for('auth.reset_with_token', token=token, _external=True)
                
                current_year = datetime.datetime.now().year
                msg = Message(
                    subject="Bem-vindo ao Estudo da Lei Seca! Crie sua senha de acesso",
                    sender=current_app.config['MAIL_DEFAULT_SENDER'],
                    recipients=[customer_email]
                )
                msg.html = render_template(
                    'auth/welcome_and_set_password_email.html',
                    set_password_url=set_password_url,
                    user_name=customer_name,
                    current_year=current_year
                )

                try:
                    db.session.commit()
                    mail.send(msg)
                    logging.info(f"Nova conta para {customer_email} criada e e-mail de boas-vindas enviado.")
                except Exception as e:
                    logging.error(f"Erro ao criar novo usuário ou enviar e-mail para {customer_email}: {e}")
                    db.session.rollback()

    # =====================================================================
    # <<< INÍCIO DA IMPLEMENTAÇÃO: LÓGICA PARA LIDAR COM CANCELAMENTOS E FALHAS >>>
    # =====================================================================
    elif event['type'] in ['customer.subscription.deleted', 'invoice.payment_failed']:
        customer_email = None
        event_type = event['type']

        # Tentamos obter o e-mail do cliente a partir do objeto do evento
        # A estrutura do payload pode variar um pouco entre os tipos de evento
        if 'customer_email' in event['data']['object']:
             customer_email = event['data']['object']['customer_email']
        elif 'customer' in event['data']['object']:
            try:
                # O objeto 'customer' pode conter o ID do cliente, não o e-mail direto.
                # Então, buscamos os detalhes do cliente no Stripe usando o ID.
                customer_id = event['data']['object']['customer']
                customer_obj = stripe.Customer.retrieve(customer_id)
                customer_email = customer_obj.get('email')
            except Exception as e:
                logging.error(f"Não foi possível obter o e-mail do cliente do evento '{event_type}'. Erro: {e}")

        if customer_email:
            logging.info(f"Webhook de '{event_type}' recebido para: {customer_email}. Iniciando processo de suspensão.")
            
            user = User.query.filter_by(email=customer_email).first()

            if user:
                # A ação principal: desativar o usuário.
                if user.is_approved:
                    user.is_approved = False
                    db.session.commit()
                    logging.info(f"Usuário {customer_email} teve seu acesso SUSPENSO devido ao evento '{event_type}'.")
                else:
                    logging.info(f"Usuário {customer_email} já estava com acesso suspenso. Nenhuma ação necessária.")
            else:
                logging.warning(f"Recebido evento '{event_type}' para o e-mail {customer_email}, mas nenhum usuário foi encontrado no banco de dados.")

    # =====================================================================
    # <<< FIM DA IMPLEMENTAÇÃO >>>
    # =====================================================================
    
    else:
        # Log para outros eventos que possamos receber, mas não estamos tratando
        logging.info(f"Webhook recebido para evento não tratado: {event['type']}")
    
    return 'OK', 200
