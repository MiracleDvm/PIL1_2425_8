# backend/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, verify_jwt_in_request
from backend.models import User, Trajet
from backend.matching import find_matches
from backend.extensions import db
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    """Page d'accueil"""
    return render_template('index.html')

@bp.route('/inscription', methods=['GET', 'POST'])
def inscription():
    """Gestion de l'inscription des utilisateurs"""
    if request.method == 'POST':
        try:
            data = request.form
            
            # Validation des champs obligatoires
            required_fields = ['nom', 'prenom', 'telephone', 'email', 'mot_de_passe']
            for field in required_fields:
                if not data.get(field) or not data.get(field).strip():
                    flash(f"Le champ {field} est obligatoire.", "danger")
                    return render_template('signup.html')
            
            # Validation de l'email
            email = data.get('email').strip().lower()
            if '@' not in email or '.' not in email:
                flash("Format d'email invalide.", "danger")
                return render_template('signup.html')
            
            # Vérification de l'unicité de l'email et du téléphone
            existing_user = User.query.filter(
                (User.email == email) | (User.telephone == data.get('telephone'))
            ).first()
            
            if existing_user:
                flash("Email ou téléphone déjà utilisé.", "danger")
                return render_template('signup.html')
            
            # Création du nouvel utilisateur
            new_user = User(
                nom=data.get('nom').strip(),
                prenom=data.get('prenom').strip(),
                telephone=data.get('telephone').strip(),
                email=email,
                role=data.get('role', 'passager'),
                point_depart=data.get('point_depart', '').strip(),
                horaires=data.get('horaires', '').strip(),
                photo=data.get('photo', '').strip()
            )
            new_user.set_password(data.get('mot_de_passe'))
            
            db.session.add(new_user)
            db.session.commit()
            
            logger.info(f"Nouvel utilisateur inscrit: {email}")
            flash("Inscription réussie ! Veuillez vous connecter.", "success")
            return redirect(url_for('main.login'))
            
        except Exception as e:
            logger.error(f"Erreur lors de l'inscription: {str(e)}")
            db.session.rollback()
            flash("Une erreur est survenue lors de l'inscription. Veuillez réessayer.", "danger")
            return render_template('signup.html')
    
    return render_template('signup.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Gestion de la connexion des utilisateurs"""
    if request.method == 'POST':
        try:
            data = request.form
            email = data.get('email', '').strip().lower()
            password = data.get('mot_de_passe', '')
            
            # Validation des champs
            if not email or not password:
                flash("Email et mot de passe sont obligatoires.", "danger")
                return render_template('login.html')
            
            # Recherche de l'utilisateur
            user = User.query.filter_by(email=email).first()
            
            if user and user.check_password(password):
                access_token = create_access_token(identity=user.id)
                logger.info(f"Connexion réussie pour: {email}")
                flash("Connexion réussie !", "success")
                
                response = make_response(redirect(url_for('main.profile')))
                response.set_cookie('access_token_cookie', access_token, 
                                  httponly=True, samesite='Lax', secure=False)
                return response
            else:
                logger.warning(f"Tentative de connexion échouée pour: {email}")
                flash("Identifiants incorrects.", "danger")
                return render_template('login.html')
                
        except Exception as e:
            logger.error(f"Erreur lors de la connexion: {str(e)}")
            flash("Une erreur est survenue lors de la connexion.", "danger")
            return render_template('login.html')
    
    return render_template('login.html')

@bp.route('/logout')
@jwt_required()
def logout():
    """Déconnexion de l'utilisateur"""
    response = make_response(redirect(url_for('main.index')))
    response.set_cookie('access_token_cookie', '', expires=0)
    flash("Déconnexion réussie.", "success")
    return response

@bp.route('/profile', methods=['GET', 'POST'])
@jwt_required()
def profile():
    """Gestion du profil utilisateur"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            flash("Utilisateur introuvable.", "danger")
            return redirect(url_for('main.login'))
        
        if request.method == 'POST':
            data = request.form
            
            # Validation des champs obligatoires
            required_fields = ['nom', 'prenom', 'telephone', 'email']
            for field in required_fields:
                if not data.get(field) or not data.get(field).strip():
                    flash(f"Le champ {field} est obligatoire.", "danger")
                    return render_template('profile.html', user=user)
            
            # Vérification de l'unicité de l'email et du téléphone (sauf pour l'utilisateur actuel)
            email = data.get('email').strip().lower()
            telephone = data.get('telephone').strip()
            
            existing_user = User.query.filter(
                ((User.email == email) | (User.telephone == telephone)) & 
                (User.id != current_user_id)
            ).first()
            
            if existing_user:
                flash("Email ou téléphone déjà utilisé par un autre utilisateur.", "danger")
                return render_template('profile.html', user=user)
            
            # Mise à jour des informations
            user.nom = data.get('nom').strip()
            user.prenom = data.get('prenom').strip()
            user.telephone = telephone
            user.email = email
            user.point_depart = data.get('point_depart', '').strip()
            user.horaires = data.get('horaires', '').strip()
            user.photo = data.get('photo', '').strip()
            
            db.session.commit()
            logger.info(f"Profil mis à jour pour l'utilisateur: {email}")
            flash("Profil mis à jour avec succès.", "success")
            
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du profil: {str(e)}")
        db.session.rollback()
        flash("Une erreur est survenue lors de la mise à jour.", "danger")
    
    return render_template('profile.html', user=user)

@bp.route('/match')
@jwt_required()
def match():
    """Recherche de correspondances pour l'utilisateur connecté"""
    try:
        current_user_id = get_jwt_identity()
        matches = find_matches(current_user_id)
        return render_template('match.html', matches=matches)
    except Exception as e:
        logger.error(f"Erreur lors de la recherche de correspondances: {str(e)}")
        flash("Une erreur est survenue lors de la recherche.", "danger")
        return redirect(url_for('main.profile'))

@bp.route('/messages')
@jwt_required()
def messages():
    """Page des messages de l'utilisateur"""
    return render_template('messages.html')

@bp.route('/trajets', methods=['GET', 'POST'])
@jwt_required()
def trajets():
    """Gestion des trajets (publication et consultation)"""
    if request.method == 'POST':
        try:
            current_user_id = get_jwt_identity()
            data = request.form
            
            # Validation des champs obligatoires
            required_fields = ['point_depart', 'point_arrivee', 'date_heure']
            for field in required_fields:
                if not data.get(field):
                    flash(f"Le champ {field} est obligatoire.", "danger")
                    return render_template('trajets.html')
            
            nouveau_trajet = Trajet(
                user_id=current_user_id,
                point_depart=data.get('point_depart').strip(),
                point_arrivee=data.get('point_arrivee').strip(),
                date_heure=data.get('date_heure'),
                places_disponibles=int(data.get('places_disponibles', 1)),
                prix=float(data.get('prix', 0.0)) if data.get('prix') else 0.0,
                description=data.get('description', '').strip()
            )
            
            db.session.add(nouveau_trajet)
            db.session.commit()
            flash("Trajet publié avec succès.", "success")
            
        except ValueError as e:
            flash("Valeurs numériques invalides.", "danger")
        except Exception as e:
            logger.error(f"Erreur lors de la publication du trajet: {str(e)}")
            db.session.rollback()
            flash("Une erreur est survenue.", "danger")
    
    # Récupération des trajets pour affichage
    trajets = Trajet.query.filter_by(actif=True).order_by(Trajet.date_heure.desc()).all()
    return render_template('trajets.html', trajets=trajets)

@bp.route('/api/user/<int:user_id>')
@jwt_required()
def get_user_api(user_id):
    """API pour récupérer les informations d'un utilisateur"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'Utilisateur non trouvé'}), 404
        
        return jsonify({
            'id': user.id,
            'nom': user.nom,
            'prenom': user.prenom,
            'email': user.email,
            'role': user.role,
            'point_depart': user.point_depart,
            'horaires': user.horaires
        })
    except Exception as e:
        logger.error(f"Erreur API get_user: {str(e)}")
        return jsonify({'error': 'Erreur serveur'}), 500

@bp.route('/test')
def test():
    """Route de test pour vérifier le fonctionnement"""
    return jsonify({
        'status': 'OK',
        'message': 'Service fonctionnel',
        'timestamp': str(db.func.now())
    })

# Gestionnaire d'erreurs
@bp.errorhandler(404)
def not_found(error):
    """Gestionnaire d'erreur 404"""
    return render_template('404.html'), 404

@bp.errorhandler(500)
def internal_error(error):
    """Gestionnaire d'erreur 500"""
    db.session.rollback()
    logger.error(f"Erreur interne: {str(error)}")
    return render_template('500.html'), 500
