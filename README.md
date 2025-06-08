# RoadOnIFRI

RoadOnIFRI est une application web de covoiturage destinée aux étudiants de l'IFRI.  
Elle permet aux utilisateurs de s'inscrire, de créer un profil, de publier et rechercher des offres de covoiturage, et d'échanger via une messagerie instantanée.

## Fonctionnalités

- **Gestion des Comptes** : Inscription, connexion (avec JWT) et gestion/modification du profil.
- **Matching de Trajets** : Un algorithme simple met en correspondance conducteurs et passagers en fonction du point de départ.
- **Messagerie Instantanée** : Communication en temps réel avec notifications via Socket.IO.
- **Interface Responsive** : Conçue avec Bootstrap et agrémentée d’animations via Animate.css.

## Technologies

- **Backend** : Python, Flask, Flask-SQLAlchemy, Flask-SocketIO, Flask-JWT-Extended
- **Frontend** : HTML, CSS (Bootstrap, Animate.css), JavaScript (Socket.IO)
- **Base de données** : SQLite (développement), MySQL/PostgreSQL (production)
- **Tests** : pytest

## Déploiement

Le projet peut être déployé via Docker. Consultez [docs/deployment_instructions.md](docs/deployment_instructions.md) pour les instructions complètes.

## Installation

1. Cloner le dépôt :
   ```bash
   git clone https://github.com/votre_nom_utilisateur/RoadOnIFRI.git
   cd RoadOnIFRI
