from flask import Blueprint, jsonify, request
from src.models.user import User, db
# NOVO: Importar a biblioteca de sanitização
import bleach

user_bp = Blueprint('user', __name__)

@user_bp.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([user.to_dict() for user in users])

@user_bp.route('/users', methods=['POST'])
def create_user():
    data = request.json
    # ALTERADO: Sanitiza os dados recebidos antes de criar o usuário
    username = bleach.clean(data.get('username'), tags=[], strip=True)
    email = bleach.clean(data.get('email'), tags=[], strip=True)
    
    user = User(username=username, email=email)
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201

@user_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())

@user_bp.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.json
    # ALTERADO: Sanitiza os dados recebidos antes de atualizar o usuário
    if 'username' in data:
        user.username = bleach.clean(data['username'], tags=[], strip=True)
    if 'email' in data:
        user.email = bleach.clean(data['email'], tags=[], strip=True)
    
    db.session.commit()
    return jsonify(user.to_dict())

@user_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return '', 204
