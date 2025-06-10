# backend/sockets.py
from flask_socketio import join_room, leave_room, emit
from flask_jwt_extended import decode_token, get_jwt_identity
from backend.models import Message, User
from backend.extensions import db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def init_socketio(socketio):
    """Initialiser les événements WebSocket"""
    
    @socketio.on('connect')
    def handle_connect(auth=None):
        """Gestion de la connexion WebSocket"""
        try:
            logger.info(f"Client connecté: {request.sid}")
            emit('connection_response', {'status': 'connected'})
        except Exception as e:
            logger.error(f"Erreur connexion WebSocket: {str(e)}")
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Gestion de la déconnexion WebSocket"""
        try:
            logger.info(f"Client déconnecté: {request.sid}")
        except Exception as e:
            logger.error(f"Erreur déconnexion WebSocket: {str(e)}")
    
    @socketio.on('join_room')
    def handle_join_room(data):
        """Rejoindre une room de chat"""
        try:
            if not data or 'room' not in data:
                emit('error', {'message': 'Room requise'})
                return
            
            room = data['room']
            username = data.get('username', 'Anonyme')
            
            join_room(room)
            
            # Notifier les autres utilisateurs
            emit('user_joined', {
                'message': f"{username} a rejoint le chat",
                'username': username,
                'timestamp': datetime.utcnow().isoformat()
            }, room=room)
            
            # Confirmer la connexion à l'utilisateur
            emit('room_joined', {
                'room': room,
                'message': f"Vous avez rejoint la room {room}"
            })
            
            logger.info(f"Utilisateur {username} a rejoint la room {room}")
            
        except Exception as e:
            logger.error(f"Erreur join_room: {str(e)}")
            emit('error', {'message': 'Erreur lors de la connexion à la room'})
    
    @socketio.on('leave_room')
    def handle_leave_room(data):
        """Quitter une room de chat"""
        try:
            if not data or 'room' not in data:
                emit('error', {'message': 'Room requise'})
                return
            
            room = data['room']
            username = data.get('username', 'Anonyme')
            
            leave_room(room)
            
            # Notifier les autres utilisateurs
            emit('user_left', {
                'message': f"{username} a quitté le chat",
                'username': username,
                'timestamp': datetime.utcnow().isoformat()
            }, room=room)
            
            logger.info(f"Utilisateur {username} a quitté la room {room}")
            
        except Exception as e:
            logger.error(f"Erreur leave_room: {str(e)}")
            emit('error', {'message': 'Erreur lors de la déconnexion de la room'})
    
    @socketio.on('send_message')
    def handle_send_message(data):
        """Envoyer un message dans une room"""
        try:
            if not data or not all(k in data for k in ['room', 'message', 'sender_id']):
                emit('error', {'message': 'Données de message incomplètes'})
                return
            
            room = data['room']
            message_content = data['message']
            sender_id = data['sender_id']
            
            # Vérifier que l'utilisateur existe
            user = User.query.get(sender_id)
            if not user:
                emit('error', {'message': 'Utilisateur non trouvé'})
                return
            
            # Sauvegarder le message en base
            new_message = Message(
                sender_id=sender_id,
                content=message_content,
                room=room
            )
            db.session.add(new_message)
            db.session.commit()
            
            # Préparer les données du message
            message_data = {
                'id': new_message.id,
                'message': message_content,
                'username': f"{user.prenom} {user.nom}",
                'sender_id': sender_id,
                'room': room,
                'timestamp': new_message.timestamp.isoformat()
            }
            
            # Diffuser le message à tous les utilisateurs de la room
            emit('receive_message', message_data, room=room)
            
            logger.info(f"Message envoyé par {user.prenom} {user.nom} dans la room {room}")
            
        except Exception as e:
            logger.error(f"Erreur send_message: {str(e)}")
            db.session.rollback()
            emit('error', {'message': 'Erreur lors de l\'envoi du message'})
    
    @socketio.on('typing')
    def handle_typing(data):
        """Gestion de l'indicateur de frappe"""
        try:
            if not data or not all(k in data for k in ['room', 'username', 'is_typing']):
                return
            
            room = data['room']
            username = data['username']
            is_typing = data['is_typing']
            
            # Diffuser l'état de frappe aux autres utilisateurs de la room
            emit('user_typing', {
                'username': username,
                'is_typing': is_typing,
                'timestamp': datetime.utcnow().isoformat()
            }, room=room, include_self=False)
            
        except Exception as e:
            logger.error(f"Erreur typing: {str(e)}")
    
    @socketio.on('get_room_users')
    def handle_get_room_users(data):
        """Récupérer la liste des utilisateurs connectés à une room"""
        try:
            if not data or 'room' not in data:
                emit('error', {'message': 'Room requise'})
                return
            
            room = data['room']
            
            # Note: En production, vous pourriez vouloir maintenir 
            # une liste des utilisateurs connectés par room
            emit('room_users', {
                'room': room,
                'users': [],  # À implémenter selon vos besoins
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Erreur get_room_users: {str(e)}")
            emit('error', {'message': 'Erreur lors de la récupération des utilisateurs'})
    
    @socketio.on_error_default
    def default_error_handler(e):
        """Gestionnaire d'erreur par défaut"""
        logger.error(f"Erreur WebSocket: {str(e)}")
        emit('error', {'message': 'Une erreur inattendue s\'est produite'})
    
    return socketio
