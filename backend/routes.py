# backend/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from backend.models import User, Trajet
from backend.matching import find_matches
from backend.extensions import db

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/inscription', methods=['GET', 'POST'])
def inscription():
    if request.method == 'POST':
        data = request.form
        # Validation simple: vérifier les champs obligatoires
        if not data.get('nom') or not data.get('prenom') or not data.get('telephone') or not data.get('email') or not data.get('mot_de_passe'):
            flash("Veuillez remplir tous les champs obligatoires.", "danger")
            return redirect(url_for('main.inscription'))
        
        # Vérifier l'unicité de l'email et du téléphone
        if User.query.filter_by(email=data.get('email')).first() or User.query.filter_by(telephone=data.get('telephone')).first():
            flash("Email ou téléphone déjà utilisé.", "danger")
            return redirect(url_for('main.inscription'))
        
        new_user = User(
            nom=data.get('nom'),
            prenom=data.get('prenom'),
            telephone=data.get('telephone'),
            email=data.get('email'),
            role=data.get('role', 'passager'),
            point_depart=data.get('point_depart'),
            horaires=data.get('horaires'),
            photo=data.get('photo')
        )
        new_user.set_password(data.get('mot_de_passe'))
        db.session.add(new_user)
        db.session.commit()
        flash("Inscription réussie ! Veuillez vous connecter.", "success")
        return redirect(url_for('main.login'))
    return render_template('signup.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.form
        email = data.get('email')
        password = data.get('mot_de_passe')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            access_token = create_access_token(identity=user.id)
            flash("Connexion réussie !", "success")
            from flask import make_response, redirect, url_for
            response = make_response(redirect(url_for('main.profile')))
            response.set_cookie('access_token_cookie', access_token, httponly=True, samesite='Lax')
            return response
        else:
            flash("Identifiants incorrects.", "danger")
            from flask import redirect, url_for
            return redirect(url_for('main.login'))
    return render_template('login.html')

@bp.route('/profile', methods=['GET', 'POST'])
@jwt_required(optional=True)
def profile():
    from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
    verify_jwt_in_request(optional=True)
    current_user_id = get_jwt_identity()
    if not current_user_id:
        flash("Vous devez être connecté pour accéder à votre profil.", "danger")
        return redirect(url_for('main.login'))
    user = User.query.get(current_user_id)
    if not user:
        flash("Utilisateur introuvable.", "danger")
        return redirect(url_for('main.login'))
    if request.method == 'POST':
        data = request.form
        user.nom = data.get('nom', user.nom)
        user.prenom = data.get('prenom', user.prenom)
        user.telephone = data.get('telephone', user.telephone)
        user.email = data.get('email', user.email)
        user.point_depart = data.get('point_depart', user.point_depart)
        user.horaires = data.get('horaires', user.horaires)
        user.photo = data.get('photo', user.photo)
        db.session.commit()
        flash("Profil mis à jour avec succès.", "success")
    return render_template('profile.html', user=user)

@bp.route('/match')
@jwt_required()
def match():
    current_user_id = get_jwt_identity()
    matches = find_matches(current_user_id)
    return render_template('index.html', matches=matches)

@bp.route('/test')
def test():
    return "Test OK"

@bp.route('/messages')
def messages():
    return render_template('messages.html')

# Vous pouvez ajouter d'autres routes pour la publication d'offres/demandes, etc.
