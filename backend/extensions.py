# backend/extensions.py
"""
Centralisation des extensions Flask pour éviter les imports circulaires
et faciliter la maintenance
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_marshmallow import Marshmallow
from flask_bcrypt import Bcrypt
import logging
import os

# Base de données
db = SQLAlchemy()

# Migrations de base de données
migrate = Migrate()

# Gestion des tokens JWT
jwt = JWTManager()

# CORS pour les requêtes cross-origin
cors = CORS()

# Rate limiting pour la sécurité
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",  # Sera remplacé par Redis en production
)

# Sérialisation/désérialisation
ma = Marshmallow()

# Hachage des mots de passe
bcrypt = Bcrypt()

# Configuration du logging
def setup_logging(app):
    """Configure le système de logging"""
    if not app.debug and not app.testing:
        # Configuration pour la production
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = logging.FileHandler('logs/roadonifri.log')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Application RoadOniFri démarrée')

# Configuration des callbacks JWT
def configure_jwt(app):
    """Configure les callbacks JWT pour la gestion des erreurs"""
    
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return {
            'message': 'Token expiré',
            'error': 'token_expired'
        }, 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return {
            'message': 'Token invalide',
            'error': 'invalid_token'
        }, 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return {
            'message': 'Token d\'autorisation requis',
            'error': 'authorization_required'
        }, 401
    
    @jwt.needs_fresh_token_loader
    def token_not_fresh_callback(jwt_header, jwt_payload):
        return {
            'message': 'Token frais requis',
            'error': 'fresh_token_required'
        }, 401
    
    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return {
            'message': 'Token révoqué',
            'error': 'token_revoked'
        }, 401

# Liste des tokens révoqués (en production, utilisez Redis)
revoked_tokens = set()

def configure_jwt_revocation():
    """Configure la révocation des tokens"""
    
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        jti = jwt_payload['jti']
        return jti in revoked_tokens

def revoke_token(jti):
    """Révoque un token"""
    revoked_tokens.add(jti)

def init_extensions(app):
    """Initialise toutes les extensions avec l'application Flask"""
    
    # Initialisation des extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, origins=app.config.get('CORS_ORIGINS', ['http://localhost:3000']))
    
    # Configuration du rate limiter
    limiter.init_app(app)
    if app.config.get('RATELIMIT_STORAGE_URL'):
        limiter.storage_uri = app.config['RATELIMIT_STORAGE_URL']
    
    ma.init_app(app)
    bcrypt.init_app(app)
    
    # Configuration des callbacks
    configure_jwt(app)
    configure_jwt_revocation()
    
    # Configuration du logging
    setup_logging(app)
    
    # Gestion des erreurs globales
    configure_error_handlers(app)

def configure_error_handlers(app):
    """Configure les gestionnaires d'erreurs globaux"""
    
    @app.errorhandler(404)
    def not_found(error):
        return {
            'message': 'Ressource non trouvée',
            'error': 'not_found'
        }, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error(f'Erreur serveur: {error}')
        return {
            'message': 'Erreur interne du serveur',
            'error': 'internal_server_error'
        }, 500
    
    @app.errorhandler(400)
    def bad_request(error):
        return {
            'message': 'Requête invalide',
            'error': 'bad_request'
        }, 400
    
    @app.errorhandler(403)
    def forbidden(error):
        return {
            'message': 'Accès interdit',
            'error': 'forbidden'
        }, 403
    
    # Gestion des erreurs de rate limiting
    @app.errorhandler(429)
    def ratelimit_handler(error):
        return {
            'message': 'Trop de requêtes. Veuillez réessayer plus tard.',
            'error': 'rate_limit_exceeded'
        }, 429

# Helper pour les tâches de base de données
def create_tables():
    """Crée toutes les tables de base de données"""
    db.create_all()

def drop_tables():
    """Supprime toutes les tables de base de données"""
    db.drop_all()

def reset_database():
    """Remet à zéro la base de données"""
    drop_tables()
    create_tables()

# Décorateurs utiles
from functools import wraps
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

def admin_required(f):
    """Décorateur pour vérifier les permissions d'administrateur"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        verify_jwt_in_request()
        current_user_id = get_jwt_identity()
        # Ici vous pourriez vérifier si l'utilisateur est admin
        # en interrogeant la base de données
        return f(*args, **kwargs)
    return decorated_function

def fresh_token_required(f):
    """Décorateur pour exiger un token frais"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        verify_jwt_in_request(fresh=True)
        return f(*args, **kwargs)
    return decorated_function
