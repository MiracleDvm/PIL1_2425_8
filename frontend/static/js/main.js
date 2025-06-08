// frontend/static/js/main.js
document.addEventListener("DOMContentLoaded", () => {
    const socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);

    socket.on('connect', () => {
        console.log("Connecté au serveur RoadOnIFRI.");
        // Rejoindre la salle de chat "global"
        socket.emit('join', { username: "Utilisateur", room: "global" });
    });

    socket.on('receive_message', data => {
        displayMessage(data, data.username === window.currentUsername);
        showNotification('Nouveau message de ' + data.username + ' !');
    });

    socket.on('join_announcement', data => {
        displayNotification(data.message);
    });

    const chatForm = document.getElementById('chat-form');
    if (chatForm) {
        chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const messageInput = document.getElementById('message-input');
            const message = messageInput.value;
            if (message.trim() === "") return;
            socket.emit('send_message', { username: "Utilisateur", message: message, room: "global" });
            messageInput.value = "";
        });
    }

    function displayMessage(data, isOwn = false) {
        const chatWindow = document.getElementById('chat-window');
        if (chatWindow) {
            const messageElem = document.createElement('div');
            messageElem.classList.add('mb-2');
            if (isOwn) messageElem.classList.add('own-message');
            messageElem.innerHTML = `<strong>${data.username}:</strong> ${data.message}`;
            chatWindow.appendChild(messageElem);
            chatWindow.scrollTop = chatWindow.scrollHeight;
        }
    }

    function displayNotification(message) {
        const chatWindow = document.getElementById('chat-window');
        if (chatWindow) {
            const notifElem = document.createElement('div');
            notifElem.classList.add('notification');
            notifElem.textContent = message;
            chatWindow.appendChild(notifElem);
            chatWindow.scrollTop = chatWindow.scrollHeight;
        }
    }

    // Notification toast en temps réel
    function showNotification(text) {
        let toast = document.createElement('div');
        toast.className = 'position-fixed top-0 end-0 p-3';
        toast.style.zIndex = 1080;
        toast.innerHTML = `<div class="toast align-items-center text-bg-primary border-0 show" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">${text}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>`;
        document.body.appendChild(toast);
        setTimeout(() => { toast.remove(); }, 2500);
    }
});
