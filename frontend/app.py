from flask import Flask, session, g, render_template, request, flash, redirect, url_for

app = Flask(__name__)
app.secret_key = 'votre_cle_secrete_a_modifier'

def get_user_by_id(user_id):
    # Fonction fictive à adapter selon votre base de données
    # Tous les champs attendus par le template profile.html sont présents
    return {
        'id': user_id,
        'nom': 'Utilisateur Test',
        'prenom': 'Prénom Test',
        'telephone': '0600000000',
        'email': 'test@example.com',
        'point_depart': 'Université',
        'horaires': '8h-18h',
        'photo': 'https://via.placeholder.com/150'
    }

@app.context_processor
def inject_user():
    user = None
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])  # À adapter selon votre code
    # Ajout d'une couleur de thème (modifiable selon vos besoins)
    theme_color = "#3498db"  # Bleu par défaut
    return dict(user=user, theme_color=theme_color)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return render_template('login.html', message="Veuillez vous connecter pour accéder à votre profil.")
    user = get_user_by_id(session['user_id'])
    if request.method == 'POST':
        # Ici, vous ajouterez la logique réelle de mise à jour du profil
        # Pour la démo, on simule la mise à jour et on affiche un message
        flash('Profil mis à jour avec succès !', 'success')  # 'success' est bien une chaîne
        # Mise à jour fictive des champs utilisateur
        user['nom'] = request.form.get('nom', user['nom'])
        user['prenom'] = request.form.get('prenom', user.get('prenom', ''))
        user['telephone'] = request.form.get('telephone', user.get('telephone', ''))
        user['email'] = request.form.get('email', user['email'])
        user['point_depart'] = request.form.get('point_depart', user.get('point_depart', ''))
        user['horaires'] = request.form.get('horaires', user.get('horaires', ''))
        user['photo'] = request.form.get('photo', user.get('photo', ''))
    return render_template('profile.html', user=user)

if __name__ == "__main__":
    app.run(debug=True)