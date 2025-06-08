# backend/sockets.py
from flask_socketio import join_room
from backend.app import socketio

@socketio.on('send_message')
def handle_send_message_event(data):
    # data doit contenir : { "username": ..., "message": ..., "room": ... }
    socketio.emit('receive_message', data, room=data['room'])

@socketio.on('join')
def handle_join_event(data):
    # data doit contenir : { "username": ..., "room": ... }
    join_room(data['room'])
    socketio.emit('join_announcement', {"message": f"{data['username']} a rejoint le chat."}, room=data['room'])
