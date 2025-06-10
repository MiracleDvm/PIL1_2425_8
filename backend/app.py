# backend/app.py
from flask import Flask, g, request
from flask_socketio import SocketIO
from flask_jwt_extended import JWTManager, get_jwt_identity, verify_jwt_in_request
from flask_cors import CORS
import os
import logging
from datetime import datetime
from backend.extensions import db
from backend.models import User

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__, 
                template_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend/templates')), 
                static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend/static')))
    
    # Configuration CORS plus sécurisée
    CORS(app, 
         origins=["http://localhost:3000", "http://127.0.0.1:5000"],
         supports_credentials=True)

    # Charger la configuration
    app.config.from_object('backend.config.Config')

    # Initialisation des extensions
    db.init_app(app)
    
    # JWT Manager
    jwt = JWTManager(app)
    
    # SocketIO - Initialisation sans import circulaire
    socketio = SocketIO(app, 
                       cors_allowed_origins=["http://localhost:3000", "http://127.0.0.1:5000"],
                       logger=True, 
                       engineio_logger=True)

    # Middleware de logging des requêtes
    @app.before_request
    def log_request_info():
        logger.info(f"Request: {request.method} {request.url} - IP: {request.remote_addr}")

    # Gestionnaire d'erreurs global
    @app.errorhandler(404)
    def not_found(error):
        return {"error": "Resource not found"}, 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal error: {str(error)}")
        db.session.rollback()
        return {"error": "Internal server error"}, 500

    @app.errorhandler(400)
    def bad_request(error):
        return {"error": "Bad request"}, 400

    # JWT Error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return {"error": "Token has expired"}, 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return {"error": "Invalid token"}, 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return {"error": "Authorization required"}, 401

    # Context processor pour l'utilisateur
    @app.context_processor
    def inject_user():
        try:
            verify_jwt_in_request(optional=True)
            user_id = get_jwt_identity()
            if user_id:
                user = User.query.get(user_id)
                return dict(user=user)
        except Exception as e:
            logger.debug(f"Context processor error: {str(e)}")
        return dict(user=None)

    # Enregistrement des blueprints
    from backend.routes import bp as main_bp
    from backend.api import bp as api_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    # Initialisation des websockets
    from backend.sockets import init_socketio
    init_socketio(socketio)

    # Diagnostic des routes
    logger.info("=== ROUTES ENREGISTRÉES ===")
    for rule in app.url_map.iter_rules():
        logger.info(f"{rule.methods} {rule.rule} -> {rule.endpoint}")
    logger.info("===========================")

    return app, socketio

# Création de l'application
app, socketio = create_app()

if __name__ == '__main__':
    # Création des tables
    with app.app_context():
        try:
            db.create_all()
            logger.info("Base de données initialisée avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de la base: {str(e)}")
    
    # Démarrage du serveur
    logger.info("Démarrage du serveur sur http://127.0.0.1:5000")
    socketio.run(app, 
                host='127.0.0.1', 
                port=5000,
                debug=True, 
                use_reloader=False)
