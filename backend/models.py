# backend/models.py
from datetime import datetime
from backend.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(50), nullable=False)
    prenom = db.Column(db.String(50), nullable=False)
    telephone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    mot_de_passe = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='passager')  # 'conducteur' ou 'passager'
    point_depart = db.Column(db.String(200))
    horaires = db.Column(db.String(50))
    photo = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.mot_de_passe = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.mot_de_passe, password)

    def __repr__(self):
        return f"<User {self.nom} {self.prenom}>"

class Trajet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conducteur_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    point_depart = db.Column(db.String(200), nullable=False)
    destination = db.Column(db.String(200), nullable=False)
    horaire_depart = db.Column(db.String(50), nullable=False)
    places_disponibles = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Trajet {self.point_depart} -> {self.destination} à {self.horaire_depart}>"

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    room = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Message from {self.sender_id} in {self.room}>"
