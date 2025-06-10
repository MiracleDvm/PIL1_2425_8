# backend/api.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from backend.models import User, Trajet, Message
from backend.matching import find_matches
from backend.extensions import db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
bp = Blueprint('api', __name__)

@bp.route('/auth/login', methods=['POST'])
def api_login():
    """API de connexion"""
    try:
        data = request.get_json()
        if not data or not data.get('email') or not data.get('password'):
            return jsonify({"error": "Email et mot de passe requis"}), 400
        
        user = User.query.filter_by(email=data.get('email')).first()
        if user and user.check_password(data.get('password')):
            access_token = create_access_token(identity=user.id)
            return jsonify({
                "message": "Connexion réussie",
                "access_token": access_token,
                "user": {
                    "id": user.id,
                    "nom": user.nom,
                    "prenom": user.prenom,
                    "email": user.email,
                    "role": user.role
                }
            }), 200
        else:
            return jsonify({"error": "Identifiants incorrects"}), 401
    except Exception as e:
        logger.error(f"Erreur login API: {str(e)}")
        return jsonify({"error": "Erreur serveur"}), 500

@bp.route('/auth/register', methods=['POST'])
def api_register():
    """API d'inscription"""
    try:
        data = request.get_json()
        required_fields = ['nom', 'prenom', 'telephone', 'email', 'password']
        
        if not data or not all(field in data for field in required_fields):
            return jsonify({"error": "Tous les champs obligatoires doivent être remplis"}), 400
        
        # Vérifier l'unicité
        if User.query.filter_by(email=data.get('email')).first():
            return jsonify({"error": "Cette adresse email est déjà utilisée"}), 409
        
        if User.query.filter_by(telephone=data.get('telephone')).first():
            return jsonify({"error": "Ce numéro de téléphone est déjà utilisé"}), 409
        
        new_user = User(
            nom=data.get('nom'),
            prenom=data.get('prenom'),
            telephone=data.get('telephone'),
            email=data.get('email'),
            role=data.get('role', 'passager'),
            point_depart=data.get('point_depart', ''),
            horaires=data.get('horaires', ''),
            photo=data.get('photo', '')
        )
        new_user.set_password(data.get('password'))
        
        db.session.add(new_user)
        db.session.commit()
        
        access_token = create_access_token(identity=new_user.id)
        
        return jsonify({
            "message": "Inscription réussie",
            "access_token": access_token,
            "user": {
                "id": new_user.id,
                "nom": new_user.nom,
                "prenom": new_user.prenom,
                "email": new_user.email,
                "role": new_user.role
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Erreur inscription API: {str(e)}")
        db.session.rollback()
        return jsonify({"error": "Erreur serveur"}), 500

@bp.route('/user/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Récupérer le profil utilisateur"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({"error": "Utilisateur non trouvé"}), 404
        
        return jsonify({
            "user": {
                "id": user.id,
                "nom": user.nom,
                "prenom": user.prenom,
                "telephone": user.telephone,
                "email": user.email,
                "role": user.role,
                "point_depart": user.point_depart,
                "horaires": user.horaires,
                "photo": user.photo,
                "created_at": user.created_at.isoformat()
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Erreur récupération profil: {str(e)}")
        return jsonify({"error": "Erreur serveur"}), 500

@bp.route('/user/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Mettre à jour le profil utilisateur"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({"error": "Utilisateur non trouvé"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Données invalides"}), 400
        
        # Vérifier l'unicité pour les champs modifiés
        if 'email' in data and data['email'] != user.email:
            if User.query.filter_by(email=data['email']).first():
                return jsonify({"error": "Cette adresse email est déjà utilisée"}), 409
        
        if 'telephone' in data and data['telephone'] != user.telephone:
            if User.query.filter_by(telephone=data['telephone']).first():
                return jsonify({"error": "Ce numéro de téléphone est déjà utilisé"}), 409
        
        # Mettre à jour les champs
        updatable_fields = ['nom', 'prenom', 'telephone', 'email', 'point_depart', 'horaires', 'photo']
        for field in updatable_fields:
            if field in data:
                setattr(user, field, data[field])
        
        db.session.commit()
        
        return jsonify({
            "message": "Profil mis à jour avec succès",
            "user": {
                "id": user.id,
                "nom": user.nom,
                "prenom": user.prenom,
                "telephone": user.telephone,
                "email": user.email,
                "role": user.role,
                "point_depart": user.point_depart,
                "horaires": user.horaires,
                "photo": user.photo
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Erreur mise à jour profil: {str(e)}")
        db.session.rollback()
        return jsonify({"error": "Erreur serveur"}), 500

@bp.route('/trajets', methods=['GET'])
def get_trajets():
    """Récupérer tous les trajets"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        if per_page > 100:
            per_page = 100
        
        trajets = Trajet.query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        return jsonify({
            "trajets": [{
                "id": trajet.id,
                "conducteur_id": trajet.conducteur_id,
                "point_depart": trajet.point_depart,
                "destination": trajet.destination,
                "horaire_depart": trajet.horaire_depart,
                "places_disponibles": trajet.places_disponibles,
                "created_at": trajet.created_at.isoformat()
            } for trajet in trajets.items],
            "pagination": {
                "page": trajets.page,
                "pages": trajets.pages,
                "per_page": trajets.per_page,
                "total": trajets.total,
                "has_next": trajets.has_next,
                "has_prev": trajets.has_prev
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Erreur récupération trajets: {str(e)}")
        return jsonify({"error": "Erreur serveur"}), 500

@bp.route('/trajets', methods=['POST'])
@jwt_required()
def create_trajet():
    """Créer un nouveau trajet"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        required_fields = ['point_depart', 'destination', 'horaire_depart']
        if not data or not all(field in data for field in required_fields):
            return jsonify({"error": "Tous les champs obligatoires doivent être remplis"}), 400
        
        new_trajet = Trajet(
            conducteur_id=current_user_id,
            point_depart=data.get('point_depart'),
            destination=data.get('destination'),
            horaire_depart=data.get('horaire_depart'),
            places_disponibles=data.get('places_disponibles', 1)
        )
        
        db.session.add(new_trajet)
        db.session.commit()
        
        return jsonify({
            "message": "Trajet créé avec succès",
            "trajet": {
                "id": new_trajet.id,
                "conducteur_id": new_trajet.conducteur_id,
                "point_depart": new_trajet.point_depart,
                "destination": new_trajet.destination,
                "horaire_depart": new_trajet.horaire_depart,
                "places_disponibles": new_trajet.places_disponibles,
                "created_at": new_trajet.created_at.isoformat()
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Erreur création trajet: {str(e)}")
        db.session.rollback()
        return jsonify({"error": "Erreur serveur"}), 500

@bp.route('/trajets/<int:trajet_id>', methods=['PUT'])
@jwt_required()
def update_trajet(trajet_id):
    """Mettre à jour un trajet"""
    try:
        current_user_id = get_jwt_identity()
        trajet = Trajet.query.get(trajet_id)
        
        if not trajet:
            return jsonify({"error": "Trajet non trouvé"}), 404
        
        if trajet.conducteur_id != current_user_id:
            return jsonify({"error": "Non autorisé à modifier ce trajet"}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Données invalides"}), 400
        
        # Mettre à jour les champs
        updatable_fields = ['point_depart', 'destination', 'horaire_depart', 'places_disponibles']
        for field in updatable_fields:
            if field in data:
                setattr(trajet, field, data[field])
        
        db.session.commit()
        
        return jsonify({
            "message": "Trajet mis à jour avec succès",
            "trajet": {
                "id": trajet.id,
                "conducteur_id": trajet.conducteur_id,
                "point_depart": trajet.point_depart,
                "destination": trajet.destination,
                "horaire_depart": trajet.horaire_depart,
                "places_disponibles": trajet.places_disponibles,
                "created_at": trajet.created_at.isoformat()
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Erreur mise à jour trajet: {str(e)}")
        db.session.rollback()
        return jsonify({"error": "Erreur serveur"}), 500

@bp.route('/trajets/<int:trajet_id>', methods=['DELETE'])
@jwt_required()
def delete_trajet(trajet_id):
    """Supprimer un trajet"""
    try:
        current_user_id = get_jwt_identity()
        trajet = Trajet.query.get(trajet_id)
        
        if not trajet:
            return jsonify({"error": "Trajet non trouvé"}), 404
        
        if trajet.conducteur_id != current_user_id:
            return jsonify({"error": "Non autorisé à supprimer ce trajet"}), 403
        
        db.session.delete(trajet)
        db.session.commit()
        
        return jsonify({"message": "Trajet supprimé avec succès"}), 200
        
    except Exception as e:
        logger.error(f"Erreur suppression trajet: {str(e)}")
        db.session.rollback()
        return jsonify({"error": "Erreur serveur"}), 500

@bp.route('/match', methods=['GET'])
@jwt_required()
def api_match():
    """API de matching"""
    try:
        current_user_id = get_jwt_identity()
        matches = find_matches(current_user_id)
        
        return jsonify({
            "matches": [{
                "id": match.id,
                "conducteur_id": match.conducteur_id,
                "point_depart": match.point_depart,
                "destination": match.destination,
                "horaire_depart": match.horaire_depart,
                "places_disponibles": match.places_disponibles,
                "created_at": match.created_at.isoformat()
            } for match in matches]
        }), 200
        
    except Exception as e:
        logger.error(f"Erreur matching API: {str(e)}")
        return jsonify({"error": "Erreur serveur"}), 500

@bp.route('/messages', methods=['GET'])
@jwt_required()
def get_messages():
    """Récupérer les messages d'une room"""
    try:
        room = request.args.get('room')
        if not room:
            return jsonify({"error": "Room requise"}), 400
        
        messages = Message.query.filter_by(room=room).order_by(Message.timestamp.desc()).limit(50).all()
        
        return jsonify({
            "messages": [{
                "id": msg.id,
                "sender_id": msg.sender_id,
                "content": msg.content,
                "room": msg.room,
                "timestamp": msg.timestamp.isoformat()
            } for msg in messages]
        }), 200
        
    except Exception as e:
        logger.error(f"Erreur récupération messages: {str(e)}")
        return jsonify({"error": "Erreur serveur"}), 500

@bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "OK", "timestamp": datetime.utcnow().isoformat()}), 200
