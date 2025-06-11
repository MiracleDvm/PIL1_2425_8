# backend/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required, 
    get_jwt_identity, get_jwt, unset_jwt_cookies
)
from marshmallow import ValidationError
from datetime import datetime, timedelta
import logging

from backend.models import User, Trajet
from backend.schemas import UserSchema, TrajetSchema, UserRegistrationSchema, UserLoginSchema
from backend.matching import find_matches
from backend.extensions import db, limiter, revoke_token
from backend.utils import validate_email, validate_phone, send_email_notification

# Configuration du logging
logger = logging.getLogger(__name__)

# Création du blueprint principal
bp = Blueprint('main', __name__)

# Schémas de validation
user_schema = UserSchema()
users_schema = UserSchema(many=True)
trajet_schema = TrajetSchema()
trajets_schema = TrajetSchema(many=True)
registration_schema = UserRegistrationSchema()
login_schema = UserLoginSchema()

@bp.route('/')
def index():
    """Page d'accueil"""
    return render_template('index.html')

@bp.route('/api/health')
def health_check():
    """Vérification de l'état de santé de l'API"""
    try:
        # Test de connexion à la base de données
        db.session.execute(db.text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'connected'
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e)
        }), 500

@bp.route('/inscription', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def inscription():
    """Gestion de l'inscription des utilisateurs"""
    if request.method == 'POST':
        try:
            # Validation des données avec Marshmallow
            if request.is_json:
                data = request.get_json()
            else:
                data = request.form.to_dict()
            
            # Validation du schéma
            validated_data = registration_schema.load(data)
            
            # Vérification de l'unicité de l'email et du téléphone
            existing_user = User.query.filter(
                (User.email == validated_data['email']) | 
                (User.telephone == validated_data['telephone'])
            ).first()
            
            if existing_user:
                error_msg = "Email ou téléphone déjà utilisé."
                if request.is_json:
                    return jsonify({'error': error_msg, 'code': 'user_exists'}), 400
                flash(error_msg, "danger")
                return render_template('signup.html')
            
            # Création du nouvel utilisateur
            new_user = User(
                nom=validated_data['nom'],
                prenom=validated_data['prenom'],
                telephone=validated_data['telephone'],
                email=validated_data['email'],
                role=validated_data.get('role', 'passager'),
                point_depart=validated_data.get('point_depart', ''),
                horaires=validated_data.get('horaires', ''),
                photo=validated_data.get('photo', '')
            )
            new_user.set_password(validated_data['mot_de_passe'])
            
            db.session.add(new_user)
            db.session.commit()
            
            logger.info(f"Nouvel utilisateur inscrit: {new_user.email}")
            
            # Envoi d'email de bienvenue (optionnel)
            try:
                send_email_notification(
                    new_user.email, 
                    "Bienvenue sur RoadOniFri", 
                    f"Bonjour {new_user.prenom}, votre inscription a été confirmée."
                )
            except Exception as e:
                logger.warning(f"Échec envoi email de bienvenue: {str(e)}")
            
            success_msg = "Inscription réussie ! Veuillez vous connecter."
            if request.is_json:
                return jsonify({
                    'message': success_msg,
                    'user_id': new_user.id
                }), 201
            
            flash(success_msg, "success")
            return redirect(url_for('main.login'))
            
        except ValidationError as e:
            error_msg = "Données invalides"
            if request.is_json:
                return jsonify({
                    'error': error_msg,
                    'details': e.messages
                }), 400
            flash(f"{error_msg}: {', '.join(e.messages.values()) if isinstance(e.messages, dict) else str(e.messages)}", "danger")
            return render_template('signup.html')
            
        except Exception as e:
            logger.error(f"Erreur lors de l'inscription: {str(e)}")
            db.session.rollback()
            error_msg = "Une erreur est survenue lors de l'inscription."
            if request.is_json:
                return jsonify({'error': error_msg}), 500
            flash(error_msg, "danger")
            return render_template('signup.html')
    
    return render_template('signup.html')

@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    """Gestion de la connexion des utilisateurs"""
    if request.method == 'POST':
        try:
            # Validation des données
            if request.is_json:
                data = request.get_json()
            else:
                data = request.form.to_dict()
            
            validated_data = login_schema.load(data)
            
            # Recherche de l'utilisateur
            user = User.query.filter_by(email=validated_data['email']).first()
            
            if user and user.check_password(validated_data['mot_de_passe']):
                # Création des tokens
                access_token = create_access_token(
                    identity=user.id,
                    additional_claims={'role': user.role}
                )
                refresh_token = create_refresh_token(identity=user.id)
                
                # Mise à jour de la dernière connexion
                user.derniere_connexion = datetime.utcnow()
                db.session.commit()
                
                logger.info(f"Connexion réussie pour: {user.email}")
                
                if request.is_json:
                    return jsonify({
                        'message': 'Connexion réussie',
                        'access_token': access_token,
                        'refresh_token': refresh_token,
                        'user': user_schema.dump(user)
                    }), 200
                
                flash("Connexion réussie !", "success")
                response = make_response(redirect(url_for('main.profile')))
                # Utiliser secure=True pour les cookies JWT en production
                response.set_cookie(
                    'access_token_cookie', 
                    access_token, 
                    httponly=True, 
                    samesite='Strict', 
                    secure=True,  # Utiliser secure=True en production avec HTTPS
                    max_age=int(timedelta(hours=1).total_seconds())
                )
                response.set_cookie(
                    'refresh_token_cookie', 
                    refresh_token, 
                    httponly=True, 
                    samesite='Strict', 
                    secure=True,
                    max_age=int(timedelta(days=30).total_seconds())
                )
                return response
            else:
                logger.warning(f"Tentative de connexion échouée pour: {validated_data['email']}")
                error_msg = "Identifiants incorrects."
                if request.is_json:
                    return jsonify({'error': error_msg, 'code': 'invalid_credentials'}), 401
                flash(error_msg, "danger")
                return render_template('login.html')
                
        except ValidationError as e:
            error_msg = "Données invalides"
            if request.is_json:
                return jsonify({
                    'error': error_msg,
                    'details': e.messages
                }), 400
            flash(error_msg, "danger")
            return render_template('login.html')
            
        except Exception as e:
            logger.error(f"Erreur lors de la connexion: {str(e)}")
            error_msg = "Une erreur est survenue lors de la connexion."
            if request.is_json:
                return jsonify({'error': error_msg}), 500
            flash(error_msg, "danger")
            return render_template('login.html')
    
    return render_template('login.html')

@bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Déconnexion de l'utilisateur"""
    try:
        # Révocation du token
        jti = get_jwt()['jti']
        revoke_token(jti)
        
        if request.is_json:
            response = jsonify({'message': 'Déconnexion réussie'})
            unset_jwt_cookies(response)
            return response, 200
        
        response = make_response(redirect(url_for('main.index')))
        unset_jwt_cookies(response)
        flash("Déconnexion réussie.", "success")
        return response
        
    except Exception as e:
        logger.error(f"Erreur lors de la déconnexion: {str(e)}")
        if request.is_json:
            return jsonify({'error': 'Erreur lors de la déconnexion'}), 500
        flash("Erreur lors de la déconnexion.", "danger")
        return redirect(url_for('main.index'))

@bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Renouvellement du token d'accès"""
    try:
        current_user_id = get_jwt_identity()
        # Récupérer le rôle de l'utilisateur pour les claims
        user = User.query.get(current_user_id)
        if not user:
            return jsonify({'error': 'Utilisateur introuvable'}), 404
            
        new_token = create_access_token(
            identity=current_user_id,
            additional_claims={'role': user.role}
        )
        
        if request.is_json:
            return jsonify({'access_token': new_token}), 200
        
        response = make_response(jsonify({'message': 'Token renouvelé'}))
        response.set_cookie(
            'access_token_cookie', 
            new_token, 
            httponly=True, 
            samesite='Strict', 
            secure=True,
            max_age=int(timedelta(hours=1).total_seconds())
        )
        return response
        
    except Exception as e:
        logger.error(f"Erreur lors du renouvellement: {str(e)}")
        return jsonify({'error': 'Erreur lors du renouvellement'}), 500

@bp.route('/profile', methods=['GET', 'POST', 'PUT'])
@jwt_required()
def profile():
    """Gestion du profil utilisateur"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            error_msg = "Utilisateur introuvable."
            if request.is_json:
                return jsonify({'error': error_msg}), 404
            flash(error_msg, "danger")
            return redirect(url_for('main.login'))
        
        if request.method == 'GET':
            if request.is_json:
                return jsonify({'user': user_schema.dump(user)}), 200
            return render_template('profile.html', user=user)
            
        elif request.method in ['POST', 'PUT']:
            # Mise à jour du profil
            if request.is_json:
                data = request.get_json()
            else:
                data = request.form.to_dict()
            
            # Validation partielle (sans mot de passe obligatoire)
            validated_data = user_schema.load(data, partial=True)
            
            # Vérification de l'unicité de l'email et du téléphone
            if 'email' in validated_data or 'telephone' in validated_data:
                email = validated_data.get('email', user.email)
                telephone = validated_data.get('telephone', user.telephone)
                
                existing_user = User.query.filter(
                    ((User.email == email) | (User.telephone == telephone)) & 
                    (User.id != current_user_id)
                ).first()
                
                if existing_user:
                    error_msg = "Email ou téléphone déjà utilisé."
                    if request.is_json:
                        return jsonify({'error': error_msg}), 400
                    flash(error_msg, "danger")
                    return render_template('profile.html', user=user)
            
            # Mise à jour des champs
            for field, value in validated_data.items():
                if hasattr(user, field) and field != 'mot_de_passe':
                    setattr(user, field, value)
            
            # Gestion du changement de mot de passe
            if 'mot_de_passe' in data and data['mot_de_passe']:
                user.set_password(data['mot_de_passe'])
            
            user.date_modification = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"Profil mis à jour pour: {user.email}")
            
            if request.is_json:
                return jsonify({
                    'message': 'Profil mis à jour avec succès',
                    'user': user_schema.dump(user)
                }), 200
            
            flash("Profil mis à jour avec succès.", "success")
            return render_template('profile.html', user=user)
            
    except ValidationError as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({
                'error': 'Données invalides',
                'details': e.messages
            }), 400
        flash("Données invalides.", "danger")
        
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du profil: {str(e)}")
        db.session.rollback()
        error_msg = "Une erreur est survenue lors de la mise à jour."
        if request.is_json:
            return jsonify({'error': error_msg}), 500
        flash(error_msg, "danger")
    
    return render_template('profile.html', user=user)

@bp.route('/match')
@jwt_required()
def match():
    """Recherche de correspondances pour l'utilisateur connecté"""
    try:
        current_user_id = get_jwt_identity()
        matches = find_matches(current_user_id)
        
        if request.is_json:
            return jsonify({
                'matches': matches,
                'count': len(matches)
            }), 200
            
        return render_template('match.html', matches=matches)
        
    except Exception as e:
        logger.error(f"Erreur lors de la recherche de correspondances: {str(e)}")
        error_msg = "Une erreur est survenue lors de la recherche."
        if request.is_json:
            return jsonify({'error': error_msg}), 500
        flash(error_msg, "danger")
        return redirect(url_for('main.profile'))

@bp.route('/trajets', methods=['GET', 'POST'])
@jwt_required()
def trajets():
    """Gestion des trajets (publication et consultation)"""
    current_user_id = get_jwt_identity()
    
    if request.method == 'POST':
        try:
            if request.is_json:
                data = request.get_json()
            else:
                data = request.form.to_dict()
            
            # Validation des données
            validated_data = trajet_schema.load(data)
            validated_data['user_id'] = current_user_id
            
            nouveau_trajet = Trajet(**validated_data)
            db.session.add(nouveau_trajet)
            db.session.commit()
            
            logger.info(f"Nouveau trajet publié par utilisateur {current_user_id}")
            
            if request.is_json:
                return jsonify({
                    'message': 'Trajet publié avec succès',
                    'trajet': trajet_schema.dump(nouveau_trajet)
                }), 201
            
            flash("Trajet publié avec succès.", "success")
            return redirect(url_for('main.trajets'))
            
        except ValidationError as e:
            db.session.rollback()
            if request.is_json:
                return jsonify({
                    'error': 'Données invalides',
                    'details': e.messages
                }), 400
            flash("Données invalides.", "danger")
            
        except Exception as e:
            logger.error(f"Erreur lors de la publication du trajet: {str(e)}")
            db.session.rollback()
            error_msg = "Une erreur est survenue."
            if request.is_json:
                return jsonify({'error': error_msg}), 500
            flash(error_msg, "danger")
    
    # Récupération des trajets
    try:
        trajets = Trajet.query.filter_by(actif=True).order_by(Trajet.date_heure.desc()).all()
        
        if request.is_json:
            return jsonify({
                'trajets': trajets_schema.dump(trajets),
                'count': len(trajets)
            }), 200
            
        return render_template('trajets.html', trajets=trajets)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des trajets: {str(e)}")
        if request.is_json:
            return jsonify({'error': 'Erreur lors de la récupération'}), 500
        return render_template('trajets.html', trajets=[])

@bp.route('/api/trajets/<int:trajet_id>', methods=['GET', 'PUT', 'DELETE'])
@jwt_required()
def trajet_detail(trajet_id):
    """Gestion d'un trajet spécifique"""
    current_user_id = get_jwt_identity()
    trajet = Trajet.query.get_or_404(trajet_id)
    
    if request.method == 'GET':
        return jsonify({'trajet': trajet_schema.dump(trajet)}), 200
    
    # Vérification des permissions
    if trajet.user_id != current_user_id:
        return jsonify({'error': 'Accès interdit'}), 403
    
    if request.method == 'PUT':
        try:
            data = request.get_json()
            validated_data = trajet_schema.load(data, partial=True)
            
            for field, value in validated_data.items():
                if hasattr(trajet, field):
                    setattr(trajet, field, value)
            
            db.session.commit()
            return jsonify({
                'message': 'Trajet mis à jour',
                'trajet': trajet_schema.dump(trajet)
            }), 200
            
        except ValidationError as e:
            return jsonify({
                'error': 'Données invalides',
                'details': e.messages
            }), 400
    
    elif request.method == 'DELETE':
        try:
            trajet.actif = False
            db.session.commit()
            return jsonify({'message': 'Trajet supprimé'}), 200
        except Exception as e:
            logger.error(f"Erreur suppression trajet: {str(e)}")
            return jsonify({'error': 'Erreur lors de la suppression'}), 500

@bp.route('/messages')
@jwt_required()
def messages():
    """Page des messages de l'utilisateur"""
    return render_template('messages.html')

@bp.route('/api/users/<int:user_id>')
@jwt_required()
def get_user_api(user_id):
    """API pour récupérer les informations d'un utilisateur"""
    try:
        user = User.query.get_or_404(user_id)
        return jsonify({'user': user_schema.dump(user)}), 200
    except Exception as e:
        logger.error(f"Erreur API get_user: {str(e)}")
        return jsonify({'error': 'Erreur serveur'}), 500

# Gestionnaires d'erreurs spécifiques au blueprint
@bp.errorhandler(404)
def not_found(error):
    """Gestionnaire d'erreur 404"""
    if request.is_json:
        return jsonify({'error': 'Ressource non trouvée'}), 404
    return render_template('404.html'), 404

@bp.errorhandler(500)
def internal_error(error):
    """Gestionnaire d'erreur 500"""
    db.session.rollback()
    logger.error(f"Erreur interne: {str(error)}")
    if request.is_json:
        return jsonify({'error': 'Erreur interne du serveur'}), 500
    return render_template('500.html'), 500
