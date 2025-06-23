# src/routes/webhook.py
from flask import Blueprint, request, abort, current_app, render_template, url_for
import stripe
import os
import logging
import datetime # <<< NOVA IMPORTAÇÃO

# ALTERADO: Importando mais ferramentas que vamos usar
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

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_email = session.get('customer_details', {}).get('email')

        if customer_email:
            logging.info(f"Webhook de pagamento bem-sucedido recebido para o e-mail: {customer_email}")
            
            user = User.query.filter_by(email=customer_email).first()

            # =====================================================================
            # <<< INÍCIO DA ALTERAÇÃO: Lógica para criar novo usuário >>>
            # =====================================================================
            if user:
                # Cenário 1: Usuário já existia (ex: se cadastrou antes de pagar)
                # Apenas aprova a conta dele.
                if not user.is_approved:
                    user.is_approved = True
                    db.session.commit()
                    logging.info(f"Usuário existente {customer_email} aprovado com sucesso via Webhook.")
                else:
                    logging.info(f"Usuário {customer_email} já estava aprovado. Nenhuma ação necessária.")
            else:
                # Cenário 2: Usuário não existe. Vamos criar a conta para ele!
                logging.info(f"Nenhum usuário encontrado para {customer_email}. Criando nova conta...")
                
                # Pega o nome do cliente do Stripe, se disponível
                customer_name = session.get('customer_details', {}).get('name', 'Aluno')
                
                # Cria o novo usuário, sem senha, mas já aprovado
                new_user = User(
                    email=customer_email,
                    full_name=customer_name,
                    is_approved=True,
                    role='student'
                )
                db.session.add(new_user)

                # Gera um token para ele criar a senha (reaproveitando nossa lógica)
                serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
                token = serializer.dumps(customer_email, salt=current_app.config['SECURITY_PASSWORD_SALT'])
                set_password_url = url_for('auth.reset_with_token', token=token, _external=True)
                
                # Prepara o e-mail de boas-vindas
                current_year = datetime.datetime.now().year
                msg = Message(
                    subject="Bem-vindo ao Estudo da Lei Seca! Crie sua senha de acesso",
                    sender=current_app.config['MAIL_DEFAULT_SENDER'],
                    recipients=[customer_email]
                )
                # IMPORTANTE: Usaremos um novo template de e-mail que ainda vamos criar
                msg.html = render_template(
                    'auth/welcome_and_set_password_email.html',
                    set_password_url=set_password_url,
                    user_name=customer_name,
                    current_year=current_year
                )

                try:
                    # Salva o novo usuário no banco e envia o e-mail
                    db.session.commit()
                    mail.send(msg)
                    logging.info(f"Nova conta para {customer_email} criada e e-mail de boas-vindas enviado.")
                except Exception as e:
                    logging.error(f"Erro ao criar novo usuário ou enviar e-mail para {customer_email}: {e}")
                    db.session.rollback()

            # =====================================================================
            # <<< FIM DA ALTERAÇÃO >>>
            # =====================================================================
    
    return 'OK', 200
