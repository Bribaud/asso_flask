# Mon Association – Site Flask

Site web de votre association, inspiré de Sene Asso, développé avec Flask (Python).

## 🚀 Démarrage rapide

```bash
# 1. Créer un environnement virtuel
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Lancer le serveur de développement
python app.py
# → http://127.0.0.1:5000
```

## 📁 Structure du projet

```
asso_flask/
├── app.py                  ← Application Flask (routes + données)
├── requirements.txt        ← Dépendances Python
├── templates/
│   ├── base.html           ← Gabarit principal (nav + footer)
│   ├── index.html          ← Page d'accueil
│   ├── presentation.html   ← À propos / équipe
│   ├── projets.html        ← Liste des projets
│   ├── projet_detail.html  ← Détail d'un projet
│   ├── actualites.html     ← Liste des actualités
│   ├── actualite_detail.html
│   ├── contact.html        ← Formulaire de contact
│   ├── adhesion.html       ← Formulaire d'adhésion
│   └── don.html            ← Page de don
├── static/
│   ├── css/style.css       ← Tous les styles
│   ├── js/main.js          ← JavaScript (burger menu, flash…)
│   └── images/             ← Mettre vos photos ici
└── data/                   ← (optionnel) Fichiers JSON de données
```

## ✏️ Personnalisation

### Changer le nom de l'association
Dans `base.html`, remplacez `MON<span class="accent">ASSO</span>` par votre nom.

### Ajouter un logo
Dans `base.html` (section `.logo`), décommentez la balise `<img>` et mettez le chemin de votre logo.

### Modifier les données (membres, projets, actualités)
Tout est dans `app.py` dans les listes `MEMBRES_CA`, `PROJETS`, `ACTUALITES`.
Pour un site plus avancé, remplacez-les par une base de données SQLite avec Flask-SQLAlchemy.

### Ajouter des photos
Déposez vos images dans `static/images/` puis référencez-les dans `app.py`.

### Couleurs
Dans `static/css/style.css`, modifiez les variables CSS au début du fichier :
- `--green` : couleur principale
- `--gold`  : couleur accent (page don)

## 🔧 Prochaines étapes suggérées

- [ ] Remplacer les données en dur par SQLite + Flask-SQLAlchemy
- [ ] Ajouter Flask-Mail pour envoyer les e-mails de contact
- [ ] Intégrer Stripe pour les paiements
- [ ] Ajouter un panneau d'administration (Flask-Admin)
- [ ] Déployer sur PythonAnywhere ou Render
