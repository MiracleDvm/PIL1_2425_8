# backend/matching.py

def find_matches(user_id):
    from backend.models import User, Trajet
    """
    Fonction de matching simple :
    - Récupère le point_depart de l'utilisateur
    - Recherche tous les trajets dont le point de départ correspond (exemple basique)
    Pour une solution avancée, intégrer une API de géolocalisation et comparer les distances.
    """
    user = User.query.get(user_id)
    if not user or not user.point_depart:
        return []
    # Recherche des trajets avec un point_depart similaire
    matches = Trajet.query.filter(Trajet.point_depart.ilike(f"%{user.point_depart}%")).all()
    return matches
