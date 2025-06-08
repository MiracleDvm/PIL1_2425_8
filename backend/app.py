# backend/app.py
from flask import Flask, g
from flask_socketio import SocketIO
from flask_jwt_extended import JWTManager, get_jwt_identity, verify_jwt_in_request
from flask_cors import CORS
import os
from backend.extensions import db
from backend.models import User

app = Flask(__name__, template_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend/templates')), static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend/static')))
CORS(app)

# Charger la configuration depuis config.py
app.config.from_object('backend.config.Config')

# Initialisation des extensions
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")
jwt = JWTManager(app)

# Importer les modules de l’application
from backend.routes import bp
app.register_blueprint(bp)

# Diagnostic : afficher toutes les routes enregistrées
print("=== ROUTES ===")
for rule in app.url_map.iter_rules():
    print(rule)
print("==============")

from backend import models, sockets, matching
print("[DEBUG] Blueprints, models, sockets, matching imported!")

from flask import g
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from backend.models import User

@app.context_processor
def inject_user():
    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if user_id:
            user = User.query.get(user_id)
            return dict(user=user)
    except Exception:
        pass
    return dict(user=None)

if __name__ == '__main__':
    # Création des tables si elles n'existent pas
    with app.app_context():
        db.create_all()
    socketio.run(app, host='127.0.0.1', use_reloader=False)
