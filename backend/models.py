# backend/models.py
from datetime import datetime
from backend.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import event
import re

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(50), nullable=False, index=True)
    prenom = db.Column(db.String(50), nullable=False, index=True)
    telephone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    mot_de_passe = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='passager', index=True)  # 'conducteur' ou 'passager'
    point_depart = db.Column(db.String(200), index=True)
    horaires = db.Column(db.String(50))
    photo = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True, index=True)
    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(100))
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    trajets_conducteur = db.relationship('Trajet', foreign_keys='Trajet.conducteur_id', backref='conducteur', lazy='dynamic')
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    reservations = db.relationship('Reservation', foreign_keys='Reservation.passager_id', backref='passager', lazy='dynamic')
    evaluations_donnees = db.relationship('Evaluation', foreign_keys='Evaluation.evaluateur_id', backref='evaluateur', lazy='dynamic')
    evaluations_recues = db.relationship('Evaluation', foreign_keys='Evaluation.evalue_id', backref='evalue', lazy='dynamic')

    def set_password(self, password):
        """Hash et stocke le mot de passe"""
        if len(password) < 6:
            raise ValueError("Le mot de passe doit contenir au moins 6 caractères")
        self.mot_de_passe = generate_password_hash(password)

    def check_password(self, password):
        """Vérifie le mot de passe"""
        return check_password_hash(self.mot_de_passe, password)
    
    def is_email_valid(self):
        """Valide le format de l'email"""
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_regex, self.email) is not None
    
    def is_phone_valid(self):
        """Valide le format du téléphone"""
        # Format simple pour les numéros béninois/africains
        phone_regex = r'^\+?[0-9]{8,15}$'
        return re.match(phone_regex, self.telephone.replace(' ', '').replace('-', '')) is not None
    
    def get_full_name(self):
        """Retourne le nom complet"""
        return f"{self.prenom} {self.nom}"
    
    def get_average_rating(self):
        """Calcule la note moyenne de l'utilisateur"""
        evaluations = self.evaluations_recues.all()
        if not evaluations:
            return None
        return sum(eval.note for eval in evaluations) / len(evaluations)
    
    def get_completed_trips_count(self):
        """Compte le nombre de trajets complétés"""
        if self.role == 'conducteur':
            return self.trajets_conducteur.filter_by(statut='complete').count()
        else:
            return self.reservations.filter_by(statut='complete').count()
    
    def to_dict(self, include_sensitive=False):
        """Convertit l'utilisateur en dictionnaire"""
        data = {
            'id': self.id,
            'nom': self.nom,
            'prenom': self.prenom,
            'email': self.email if include_sensitive else None,
            'telephone': self.telephone if include_sensitive else None,
            'role': self.role,
            'point_depart': self.point_depart,
            'horaires': self.horaires,
            'photo': self.photo,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'average_rating': self.get_average_rating(),
            'completed_trips': self.get_completed_trips_count()
        }
        return {k: v for k, v in data.items() if v is not None}

    def __repr__(self):
        return f"<User {self.get_full_name()}>"

class Trajet(db.Model):
    __tablename__ = 'trajets'
    
    id = db.Column(db.Integer, primary_key=True)
    conducteur_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    point_depart = db.Column(db.String(200), nullable=False, index=True)
    destination = db.Column(db.String(200), nullable=False, index=True)
    horaire_depart = db.Column(db.String(50), nullable=False)
    date_trajet = db.Column(db.Date)
    places_disponibles = db.Column(db.Integer, default=1)
    places_totales = db.Column(db.Integer, default=1)
    prix_par_place = db.Column(db.Float, default=0.0)
    description = db.Column(db.Text)
    statut = db.Column(db.String(20), default='active', index=True)  # 'active', 'complete', 'cancelled'
    type_trajet = db.Column(db.String(20), default='ponctuel')  # 'ponctuel', 'regulier'
    jours_semaine = db.Column(db.String(20))  # Pour les trajets réguliers: 'lundi,mardi,mercredi'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    reservations = db.relationship('Reservation', backref='trajet', lazy='dynamic', cascade='all, delete-orphan')
    
    @property
    def places_reservees(self):
        """Calcule le nombre de places réservées"""
        return self.reservations.filter_by(statut='confirmee').count()
    
    @property
    def places_libres(self):
        """Calcule le nombre de places libres"""
        return max(0, self.places_disponibles - self.places_reservees)
    
    def is_available(self):
        """Vérifie si le trajet est disponible pour réservation"""
        return (self.statut == 'active' and 
                self.places_libres > 0 and 
                (not self.date_trajet or self.date_trajet >= datetime.now().date()))
    
    def can_be_modified_by(self, user_id):
        """Vérifie si un utilisateur peut modifier ce trajet"""
        return self.conducteur_id == user_id and self.statut == 'active'
    
    def get_distance_estimate(self):
        """Estimation simple de distance (à améliorer avec une vraie API)"""
        # Logique simplifiée - à remplacer par une vraie API de géolocalisation
        return "Distance non calculée"
    
    def to_dict(self, include_conducteur=False):
        """Convertit le trajet en dictionnaire"""
        data = {
            'id': self.id,
            'conducteur_id': self.conducteur_id,
            'point_depart': self.point_depart,
            'destination': self.destination,
            'horaire_depart': self.horaire_depart,
            'date_trajet': self.date_trajet.isoformat() if self.date_trajet else None,
            'places_disponibles': self.places_disponibles,
            'places_libres': self.places_libres,
            'prix_par_place': self.prix_par_place,
            'description': self.description,
            'statut': self.statut,
            'type_trajet': self.type_trajet,
            'jours_semaine': self.jours_semaine,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_available': self.is_available()
        }
        
        if include_conducteur and self.conducteur:
            data['conducteur'] = self.conducteur.to_dict()
        
        return data

    def __repr__(self):
        return f"<Trajet {self.point_depart} -> {self.destination} à {self.horaire_depart}>"

class Reservation(db.Model):
    __tablename__ = 'reservations'
    
    id = db.Column(db.Integer, primary_key=True)
    trajet_id = db.Column(db.Integer, db.ForeignKey('trajets.id'), nullable=False, index=True)
    passager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    nombre_places = db.Column(db.Integer, default=1)
    statut = db.Column(db.String(20), default='en_attente', index=True)  # 'en_attente', 'confirmee', 'annulee', 'complete'
    message = db.Column(db.Text)  # Message du passager au conducteur
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def can_be_cancelled(self):
        """Vérifie si la réservation peut être annulée"""
        return self.statut in ['en_attente', 'confirmee']
    
    def to_dict(self, include_relations=False):
        """Convertit la réservation en dictionnaire"""
        data = {
            'id': self.id,
            'trajet_id': self.trajet_id,
            'passager_id': self.passager_id,
            'nombre_places': self.nombre_places,
            'statut': self.statut,
            'message': self.message,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_relations:
            if self.trajet:
                data['trajet'] = self.trajet.to_dict()
            if self.passager:
                data['passager'] = self.passager.to_dict()
        
        return data

    def __repr__(self):
        return f"<Reservation {self.passager_id} -> Trajet {self.trajet_id}>"

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)  # Pour messages privés
    content = db.Column(db.Text, nullable=False)
    room = db.Column(db.String(50), nullable=False, index=True)
    message_type = db.Column(db.String(20), default='text')  # 'text', 'image', 'location'
    is_read = db.Column(db.Boolean, default=False, index=True)
    trajet_id = db.Column(db.Integer, db.ForeignKey('trajets.id'), index=True)  # Lien optionnel vers un trajet
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def mark_as_read(self):
        """Marque le message comme lu"""
        self.is_read = True
        db.session.commit()
    
    def to_dict(self, include_sender=False):
        """Convertit le message en dictionnaire"""
        data = {
            'id': self.id,
            'sender_id': self.sender_id,
            'recipient_id': self.recipient_id,
            'content': self.content,
            'room': self.room,
            'message_type': self.message_type,
            'is_read': self.is_read,
            'trajet_id': self.trajet_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
        
        if include_sender and self.sender:
            data['sender'] = {
                'id': self.sender.id,
                'nom': self.sender.nom,
                'prenom': self.sender.prenom,
                'photo': self.sender.photo
            }
        
        return data

    def __repr__(self):
        return f"<Message from {self.sender_id} in {self.room}>"

class Evaluation(db.Model):
    __tablename__ = 'evaluations'
    
    id = db.Column(db.Integer, primary_key=True)
    evaluateur_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    evalue_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    trajet_id = db.Column(db.Integer, db.ForeignKey('trajets.id'), nullable=False, index=True)
    note = db.Column(db.Integer, nullable=False)  # 1 à 5 étoiles
    commentaire = db.Column(db.Text)
    criteres = db.Column(db.JSON)  # {'ponctualite': 5, 'amabilite': 4, 'securite': 5}
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<Evaluation {self.note}/5 de {self.evaluateur_id} vers {self.evalue_id}>"

# Événements SQLAlchemy pour validation automatique
@event.listens_for(User, 'before_insert')
@event.listens_for(User, 'before_update')
def validate_user(mapper, connection, target):
    """Validation automatique des données utilisateur"""
    if not target.is_email_valid():
        raise ValueError(f"Format d'email invalide: {target.email}")
    
    if not target.is_phone_valid():
        raise ValueError(f"Format de téléphone invalide: {target.telephone}")

@event.listens_for(Evaluation, 'before_insert')
@event.listens_for(Evaluation, 'before_update')
def validate_evaluation(mapper, connection, target):
    """Validation automatique des évaluations"""
    if not (1 <= target.note <= 5):
        raise ValueError("La note doit être comprise entre 1 et 5")
    
    if target.evaluateur_id == target.evalue_id:
        raise ValueError("Un utilisateur ne peut pas s'auto-évaluer")
