# backend/matching.py
from backend.models import User, Trajet
from backend.extensions import db
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def calculate_text_similarity(text1, text2):
    """
    Calcule la similarité entre deux textes (simplifiée).
    Retourne un score entre 0 et 1.
    """
    if not text1 or not text2:
        return 0.0
    
    text1_lower = text1.lower()
    text2_lower = text2.lower()
    
    # Similarité exacte
    if text1_lower == text2_lower:
        return 1.0
    
    # Similarité partielle (contient)
    if text1_lower in text2_lower or text2_lower in text1_lower:
        return 0.8
    
    # Mots communs
    words1 = set(text1_lower.split())
    words2 = set(text2_lower.split())
    
    if not words1 or not words2:
        return 0.0
    
    common_words = words1.intersection(words2)
    total_words = words1.union(words2)
    
    if total_words:
        return len(common_words) / len(total_words)
    
    return 0.0

def parse_time_preference(horaires):
    """
    Parse les préférences horaires (format simple).
    Retourne une liste d'heures préférées.
    """
    if not horaires:
        return []
    
    # Formats supportés: "8h-10h", "matin", "soir", "8h", etc.
    horaires_lower = horaires.lower()
    preferences = []
    
    if 'matin' in horaires_lower:
        preferences.extend([6, 7, 8, 9, 10])
    elif 'midi' in horaires_lower:
        preferences.extend([11, 12, 13, 14])
    elif 'soir' in horaires_lower:
        preferences.extend([17, 18, 19, 20, 21])
    elif 'nuit' in horaires_lower:
        preferences.extend([22, 23, 0, 1, 2])
    
    # Extraction d'heures spécifiques (8h, 14h30, etc.)
    import re
    time_pattern = r'(\d{1,2})h?(\d{0,2})?'
    matches = re.findall(time_pattern, horaires_lower)
    
    for match in matches:
        try:
            hour = int(match[0])
            if 0 <= hour <= 23:
                preferences.append(hour)
        except ValueError:
            continue
    
    return list(set(preferences))  # Supprime les doublons

def calculate_time_compatibility(user_horaires, trajet_horaire):
    """
    Calcule la compatibilité horaire entre un utilisateur et un trajet.
    """
    if not user_horaires or not trajet_horaire:
        return 0.5  # Score neutre si pas d'info
    
    user_preferences = parse_time_preference(user_horaires)
    
    # Essayer d'extraire l'heure du trajet
    try:
        # Format attendu: "8h30", "14h", "08:30", etc.
        import re
        time_match = re.search(r'(\d{1,2})[h:]?(\d{0,2})?', trajet_horaire.lower())
        if time_match:
            trajet_hour = int(time_match.group(1))
            
            if not user_preferences:
                return 0.5
            
            # Vérifier si l'heure du trajet correspond aux préférences
            for pref_hour in user_preferences:
                if abs(trajet_hour - pref_hour) <= 1:  # Tolérance de 1h
                    return 1.0
                elif abs(trajet_hour - pref_hour) <= 2:  # Tolérance de 2h
                    return 0.7
            
            return 0.3  # Horaire possible mais pas optimal
    except:
        pass
    
    return 0.5

def find_matches(user_id, limit=10):
    """
    Trouve les trajets compatibles pour un utilisateur.
    Algorithme de matching amélioré avec scoring.
    """
    try:
        user = User.query.get(user_id)
        if not user:
            logger.warning(f"Utilisateur {user_id} non trouvé pour le matching")
            return []
        
        # Récupérer tous les trajets disponibles (pas créés par l'utilisateur)
        trajets = Trajet.query.filter(
            Trajet.conducteur_id != user_id,
            Trajet.places_disponibles > 0
        ).all()
        
        if not trajets:
            logger.info(f"Aucun trajet disponible pour le matching de l'utilisateur {user_id}")
            return []
        
        matches_with_score = []
        
        for trajet in trajets:
            score = 0.0
            reasons = []
            
            # 1. Compatibilité géographique (point de départ)
            if user.point_depart and trajet.point_depart:
                geo_score = calculate_text_similarity(user.point_depart, trajet.point_depart)
                score += geo_score * 0.4  # 40% du score total
                if geo_score > 0.7:
                    reasons.append(f"Point de départ similaire ({geo_score:.1%})")
            
            # 2. Compatibilité horaire
            if user.horaires and trajet.horaire_depart:
                time_score = calculate_time_compatibility(user.horaires, trajet.horaire_depart)
                score += time_score * 0.3  # 30% du score total
                if time_score > 0.7:
                    reasons.append(f"Horaires compatibles ({time_score:.1%})")
            
            # 3. Disponibilité des places
            places_score = min(trajet.places_disponibles / 4, 1.0)  # Normalisation sur 4 places max
            score += places_score * 0.1  # 10% du score total
            
            # 4. Récence du trajet (favoriser les trajets récents)
            if trajet.created_at:
                days_ago = (datetime.utcnow() - trajet.created_at).days
                recency_score = max(0, 1 - (days_ago / 30))  # Score diminue sur 30 jours
                score += recency_score * 0.1  # 10% du score total
            
            # 5. Bonus si même rôle (conducteur cherche passager ou vice versa)
            if user.role == 'passager':  # Passager cherche des trajets de conducteurs
                score += 0.1  # 10% bonus
                reasons.append("Vous cherchez un trajet")
            
            # Filtrer les matches avec un score minimum
            if score > 0.3:  # Seuil de pertinence
                matches_with_score.append({
                    'trajet': trajet,
                    'score': score,
                    'reasons': reasons
                })
        
        # Trier par score décroissant
        matches_with_score.sort(key=lambda x: x['score'], reverse=True)
        
        # Limiter le nombre de résultats
        matches_with_score = matches_with_score[:limit]
        
        # Retourner seulement les trajets (pour compatibilité)
        matches = [match['trajet'] for match in matches_with_score]
        
        logger.info(f"Matching pour utilisateur {user_id}: {len(matches)} trajets trouvés")
        
        return matches
        
    except Exception as e:
        logger.error(f"Erreur lors du matching pour utilisateur {user_id}: {str(e)}")
        return []

def find_detailed_matches(user_id, limit=10):
    """
    Version détaillée du matching qui retourne les scores et raisons.
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return []
        
        trajets = Trajet.query.filter(
            Trajet.conducteur_id != user_id,
            Trajet.places_disponibles > 0
        ).all()
        
        if not trajets:
            return []
        
        matches_with_score = []
        
        for trajet in trajets:
            score = 0.0
            reasons = []
            
            # Logique de scoring identique à find_matches
            if user.point_depart and trajet.point_depart:
                geo_score = calculate_text_similarity(user.point_depart, trajet.point_depart)
                score += geo_score * 0.4
                if geo_score > 0.7:
                    reasons.append(f"Point de départ similaire ({geo_score:.1%})")
            
            if user.horaires and trajet.horaire_depart:
                time_score = calculate_time_compatibility(user.horaires, trajet.horaire_depart)
                score += time_score * 0.3
                if time_score > 0.7:
                    reasons.append(f"Horaires compatibles ({time_score:.1%})")
            
            places_score = min(trajet.places_disponibles / 4, 1.0)
            score += places_score * 0.1
            
            if trajet.created_at:
                days_ago = (datetime.utcnow() - trajet.created_at).days
                recency_score = max(0, 1 - (days_ago / 30))
                score += recency_score * 0.1
            
            if user.role == 'passager':
                score += 0.1
                reasons.append("Vous cherchez un trajet")
            
            if score > 0.3:
                # Récupérer les infos du conducteur
                conducteur = User.query.get(trajet.conducteur_id)
                
                matches_with_score.append({
                    'trajet': {
                        'id': trajet.id,
                        'point_depart': trajet.point_depart,
                        'destination': trajet.destination,
                        'horaire_depart': trajet.horaire_depart,
                        'places_disponibles': trajet.places_disponibles,
                        'created_at': trajet.created_at.isoformat(),
                        'conducteur': {
                            'id': conducteur.id,
                            'nom': conducteur.nom,
                            'prenom': conducteur.prenom,
                            'photo': conducteur.photo
                        } if conducteur else None
                    },
                    'score': round(score, 2),
                    'reasons': reasons,
                    'compatibility_percentage': round(score * 100, 1)
                })
        
        # Trier par score décroissant
        matches_with_score.sort(key=lambda x: x['score'], reverse=True)
        
        return matches_with_score[:limit]
        
    except Exception as e:
        logger.error(f"Erreur lors du matching détaillé pour utilisateur {user_id}: {str(e)}")
        return []

def find_reverse_matches(user_id, limit=10):
    """
    Trouve les utilisateurs qui pourraient être intéressés par les trajets de l'utilisateur.
    Utile pour les conducteurs qui veulent voir qui pourrait être intéressé.
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return []
        
        # Récupérer les trajets de l'utilisateur
        user_trajets = Trajet.query.filter_by(conducteur_id=user_id).all()
        if not user_trajets:
            return []
        
        # Récupérer les autres utilisateurs (potentiels passagers)
        potential_passengers = User.query.filter(
            User.id != user_id,
            User.role == 'passager'
        ).all()
        
        reverse_matches = []
        
        for trajet in user_trajets:
            for passenger in potential_passengers:
                score = 0.0
                reasons = []
                
                # Compatibilité géographique
                if passenger.point_depart and trajet.point_depart:
                    geo_score = calculate_text_similarity(passenger.point_depart, trajet.point_depart)
                    score += geo_score * 0.4
                    if geo_score > 0.7:
                        reasons.append(f"Point de départ compatible")
                
                # Compatibilité horaire
                if passenger.horaires and trajet.horaire_depart:
                    time_score = calculate_time_compatibility(passenger.horaires, trajet.horaire_depart)
                    score += time_score * 0.3
                    if time_score > 0.7:
                        reasons.append(f"Horaires compatibles")
                
                if score > 0.4:  # Seuil plus élevé pour les reverse matches
                    reverse_matches.append({
                        'passenger': {
                            'id': passenger.id,
                            'nom': passenger.nom,
                            'prenom': passenger.prenom,
                            'point_depart': passenger.point_depart,
                            'horaires': passenger.horaires,
                            'photo': passenger.photo
                        },
                        'trajet': {
                            'id': trajet.id,
                            'point_depart': trajet.point_depart,
                            'destination': trajet.destination,
                            'horaire_depart': trajet.horaire_depart
                        },
                        'score': round(score, 2),
                        'reasons': reasons
                    })
        
        # Trier par score et éliminer les doublons
        seen_passengers = set()
        unique_matches = []
        
        for match in sorted(reverse_matches, key=lambda x: x['score'], reverse=True):
            passenger_id = match['passenger']['id']
            if passenger_id not in seen_passengers:
                unique_matches.append(match)
                seen_passengers.add(passenger_id)
        
        return unique_matches[:limit]
        
    except Exception as e:
        logger.error(f"Erreur lors du reverse matching pour utilisateur {user_id}: {str(e)}")
        return []

def get_matching_statistics(user_id):
    """
    Retourne des statistiques sur le matching pour un utilisateur.
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return None
        
        total_trajets = Trajet.query.filter(Trajet.conducteur_id != user_id).count()
        available_trajets = Trajet.query.filter(
            Trajet.conducteur_id != user_id,
            Trajet.places_disponibles > 0
        ).count()
        
        matches = find_matches(user_id, limit=100)  # Récupérer plus pour les stats
        high_quality_matches = [m for m in find_detailed_matches(user_id, limit=100) if m['score'] > 0.7]
        
        stats = {
            'user_id': user_id,
            'total_trajets_available': available_trajets,
            'total_trajets_all': total_trajets,
            'total_matches': len(matches),
            'high_quality_matches': len(high_quality_matches),
            'matching_rate': round((len(matches) / available_trajets * 100) if available_trajets > 0 else 0, 1),
            'user_profile_completeness': calculate_profile_completeness(user),
            'recommendations': generate_profile_recommendations(user)
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Erreur lors du calcul des statistiques pour utilisateur {user_id}: {str(e)}")
        return None

def calculate_profile_completeness(user):
    """
    Calcule le pourcentage de complétude du profil utilisateur.
    """
    fields_to_check = ['nom', 'prenom', 'telephone', 'email', 'point_depart', 'horaires']
    completed_fields = 0
    
    for field in fields_to_check:
        if hasattr(user, field) and getattr(user, field):
            completed_fields += 1
    
    return round((completed_fields / len(fields_to_check)) * 100, 1)

def generate_profile_recommendations(user):
    """
    Génère des recommandations pour améliorer le profil.
    """
    recommendations = []
    
    if not user.point_depart:
        recommendations.append("Ajoutez votre point de départ pour améliorer le matching")
    
    if not user.horaires:
        recommendations.append("Précisez vos horaires préférés pour de meilleurs résultats")
    
    if not user.photo:
        recommendations.append("Ajoutez une photo de profil pour inspirer confiance")
    
    if len(user.point_depart or '') < 5:
        recommendations.append("Soyez plus précis dans votre localisation")
    
    return recommendations
