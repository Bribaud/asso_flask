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

## 💳 Stripe (production)

Variables d'environnement à définir dans Vercel (Settings → Environment Variables) :

| Variable | Rôle |
|---|---|
| `STRIPE_SECRET_KEY` | Clé secrète (`sk_test_…` en test, `sk_live_…` en production) |
| `STRIPE_WEBHOOK_SECRET` | Secret de signature du webhook (`whsec_…`) |

Webhook à créer dans le dashboard Stripe : URL `https://asso-flask.vercel.app/stripe/webhook`,
événements `checkout.session.completed` et `checkout.session.async_payment_succeeded`.
Le webhook active les adhésions (matricule + carte par e-mail) et passe les dons en « payé ».
Les dons en FCFA sont convertis en euros (parité fixe 655,957) avant le paiement.

## 🗄️ Base de données (Supabase / PostgreSQL)

| Variable | Rôle |
|---|---|
| `DATABASE_URL` | URI PostgreSQL. Sur Vercel, utiliser le **Transaction pooler** de Supabase (port 6543) |
| `ADMIN_PASSWORD` | Mot de passe du compte `admin`, créé au premier démarrage sur une base vide |

- Sans `DATABASE_URL`, l'application utilise un SQLite temporaire (`/tmp`) : **les données sont perdues** à chaque redémarrage.
- Sans `ADMIN_PASSWORD`, aucun compte admin n'est créé (il n'y a plus de mot de passe par défaut).
- La RLS Supabase est activée automatiquement sur toutes les tables au démarrage : l'API REST publique de Supabase n'y a pas accès, seule la connexion de l'application le peut.
- En local : `ADMIN_PASSWORD=monmotdepasse python app.py` (PowerShell : `$env:ADMIN_PASSWORD="..."; python app.py`).
