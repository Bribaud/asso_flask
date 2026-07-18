from flask import (Flask, render_template, request, redirect,
                   url_for, flash, jsonify, session)
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message as MailMessage
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps
from sqlalchemy.pool import NullPool
from io import BytesIO
import stripe, os, uuid

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "akf-super-secret-key-2026")

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "sk_test_51Tcme02YF5ue5EAIOSUxkRk5kPlVLYm0raGfb2OvN35tyJuxLNNZjU6ArE3kvDWHQNKrvUkh2xN36cAXveCZ8FFv007b5S3Iks")

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:////tmp/akf.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# NullPool requis pour les environnements serverless (Vercel) avec PostgreSQL
if DATABASE_URL.startswith("postgresql"):
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "poolclass": NullPool,
    }
db = SQLAlchemy(app)

# ── MAIL ──────────────────────────────────────────────────────────────────────
app.config["MAIL_SERVER"]         = os.environ.get("MAIL_SERVER", "smtp.mail.ovh.net")
app.config["MAIL_PORT"]           = 465
app.config["MAIL_USE_TLS"]        = False
app.config["MAIL_USE_SSL"]        = True
app.config["MAIL_USERNAME"]       = os.environ.get("MAIL_USERNAME", "contact@koungheulois-france.fr")
app.config["MAIL_PASSWORD"]       = os.environ.get("MAIL_PASSWORD", "@Akf202626")
app.config["MAIL_DEFAULT_SENDER"] = ("AKF", "contact@koungheulois-france.fr")
app.config["MAIL_TIMEOUT"]        = 10
mail = Mail(app)

def send_mail_safe(msg):
    try:
        mail.send(msg)
    except (Exception, SystemExit, BaseException):
        pass

# ── UPLOAD ────────────────────────────────────────────────────────────────────
# Sur Vercel le filesystem est en lecture seule → on utilise /tmp
UPLOAD_FOLDER      = os.environ.get("UPLOAD_FOLDER", os.path.join("/tmp", "uploads"))
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
except OSError:
    pass

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_upload(file):
    if file and allowed_file(file.filename):
        ext      = file.filename.rsplit(".", 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        return filename
    return None

# ── IDENTITÉ ──────────────────────────────────────────────────────────────────
SITE_URL = "https://koungheulois-france.fr"

ASSO = {
    "nom":         "Association des Koungheulois de France",
    "nom_court":   "AKF",
    "slogan":      "Solidarité • Entraide • Développement",
    "description": (
        "L'Association des Koungheulois de France (AKF) rassemble "
        "et accompagne les ressortissants de Koungheul établis en France "
        "à travers des actions de solidarité, d'entraide et de cohésion sociale. "
        "Elle contribue également au développement de Koungheul au Sénégal "
        "dans les domaines éducatif, sanitaire, social et économique."
    ),
    "siege":       "22 Avenue des Coutures, Limoges, France",
    "rna":         "W872016956",
    "siren":       "105 083 620",
    "siret":       "105 083 620 00010",
    "fondation":   "11 mars 2026",
    "declaration": "24 avril 2026",
    "email":       "contact@koungheulois-france.fr",
    "telephone":   "+33 6 12 34 56 78",
    "facebook":    "#",
    "instagram":   "https://www.instagram.com/associationkghl2026?igsh=MWhxdGY0cThibmJvbw==",
    "tiktok":      "https://tiktok.com/@association.ds.ko",
    "site":        SITE_URL,
}

MAIL_NOTIFICATIONS = os.environ.get("MAIL_NOTIFICATIONS", "papesemoundao2016@gmail.com")

# Prix d'adhésion en centimes (configurables via variables d'environnement Vercel)
ADHESION_PRIX = {
    "etudiant":          int(os.environ.get("ADHESION_PRIX_ETUDIANT",     500)),   # 5 €
    "membre_actif":      int(os.environ.get("ADHESION_PRIX_ACTIF",       1000)),  # 10 €
    "membre_bienfaiteur": int(os.environ.get("ADHESION_PRIX_BIENFAITEUR", 2000)), # 20 €
}

# ── MODÈLES ───────────────────────────────────────────────────────────────────

class AdminUser(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    def set_password(self, p): self.password_hash = generate_password_hash(p)
    def check_password(self, p): return check_password_hash(self.password_hash, p)

class ContactMessage(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    nom           = db.Column(db.String(150), nullable=False)
    email         = db.Column(db.String(150), nullable=False)
    sujet         = db.Column(db.String(200))
    message       = db.Column(db.Text, nullable=False)
    lu            = db.Column(db.Boolean, default=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

class Don(db.Model):
    id                = db.Column(db.Integer, primary_key=True)
    nom               = db.Column(db.String(120))
    email             = db.Column(db.String(120))
    montant           = db.Column(db.Float, nullable=False)
    devise            = db.Column(db.String(10), default="EUR")
    stripe_session_id = db.Column(db.String(255))
    statut            = db.Column(db.String(20), default="en_attente")
    date_creation     = db.Column(db.DateTime, default=datetime.utcnow)

class Adhesion(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    civilite         = db.Column(db.String(10))
    prenom           = db.Column(db.String(100), nullable=False)
    nom              = db.Column(db.String(100), nullable=False)
    email            = db.Column(db.String(150), nullable=False)
    telephone        = db.Column(db.String(50))
    date_naissance   = db.Column(db.String(20))
    etudiant         = db.Column(db.String(5))
    etablissement    = db.Column(db.String(200))
    profession       = db.Column(db.String(100))
    profession_autre = db.Column(db.String(200))
    adresse          = db.Column(db.String(200))
    code_postal      = db.Column(db.String(10))
    ville            = db.Column(db.String(100))
    pays             = db.Column(db.String(100))
    type_adhesion    = db.Column(db.String(100))
    motivation       = db.Column(db.Text)
    statut           = db.Column(db.String(20), default="en_attente")
    matricule        = db.Column(db.String(20), unique=True, nullable=True)
    stripe_session_id = db.Column(db.String(255), nullable=True)
    date_creation    = db.Column(db.DateTime, default=datetime.utcnow)

class Projet(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    titre         = db.Column(db.String(200), nullable=False)
    categorie     = db.Column(db.String(80))
    description   = db.Column(db.Text)
    contenu       = db.Column(db.Text)
    image         = db.Column(db.String(200))
    slug          = db.Column(db.String(200), unique=True, nullable=False)
    publie        = db.Column(db.Boolean, default=True)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

class Actualite(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    titre         = db.Column(db.String(200), nullable=False)
    categorie     = db.Column(db.String(80))
    extrait       = db.Column(db.String(400))
    contenu       = db.Column(db.Text)
    image         = db.Column(db.String(200))
    slug          = db.Column(db.String(200), unique=True, nullable=False)
    publie        = db.Column(db.Boolean, default=True)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

class Evenement(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    titre         = db.Column(db.String(200), nullable=False)
    type_event    = db.Column(db.String(80))
    description   = db.Column(db.Text)
    lieu          = db.Column(db.String(200))
    adresse       = db.Column(db.String(300))
    date_event    = db.Column(db.DateTime, nullable=False)
    heure_fin     = db.Column(db.String(10))
    image         = db.Column(db.String(200))
    lien_externe  = db.Column(db.String(300))
    publie        = db.Column(db.Boolean, default=True)
    slug          = db.Column(db.String(200), unique=True, nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

class MembreBureau(db.Model):
    id    = db.Column(db.Integer, primary_key=True)
    nom   = db.Column(db.String(150), nullable=False)
    poste = db.Column(db.String(100))
    photo = db.Column(db.String(200))
    ordre = db.Column(db.Integer, default=0)
    actif = db.Column(db.Boolean, default=True)

class Cotisation(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    adhesion_id    = db.Column(db.Integer, db.ForeignKey("adhesion.id"), nullable=False)
    adhesion       = db.relationship("Adhesion", backref="cotisations")
    mois           = db.Column(db.Integer, nullable=False)
    annee          = db.Column(db.Integer, nullable=False)
    montant        = db.Column(db.Float, nullable=False)
    statut         = db.Column(db.String(20), default="en_attente")
    date_paiement  = db.Column(db.DateTime)
    mode_paiement  = db.Column(db.String(50))
    justificatif   = db.Column(db.String(200))
    note           = db.Column(db.String(300))
    rappel1_envoye = db.Column(db.Boolean, default=False)
    rappel2_envoye = db.Column(db.Boolean, default=False)
    alerte_envoye  = db.Column(db.Boolean, default=False)
    date_creation  = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def label_mois(self):
        mois_fr = ["","Janvier","Février","Mars","Avril","Mai","Juin",
                   "Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
        return f"{mois_fr[self.mois]} {self.annee}"

    @property
    def jours_depuis_creation(self):
        return (datetime.utcnow() - self.date_creation).days

# ── HELPERS ───────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

def make_slug(titre):
    import unicodedata, re
    s = unicodedata.normalize("NFD", titre)
    s = s.encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9\s-]", "", s).strip().lower()
    s = re.sub(r"[\s]+", "-", s)
    return s

def email_footer():
    return f"""
    <hr style="border:none;border-top:1px solid #e5e7eb;margin:28px 0">
    <div style="text-align:center;margin-bottom:20px">
      <a href="{SITE_URL}" style="background:#1a7a4a;color:#fff;padding:10px 24px;
         border-radius:8px;text-decoration:none;font-size:.85rem;font-weight:600;
         display:inline-block">Visiter notre site</a>
    </div>
    <p style="color:#9ca3af;font-size:.75rem;text-align:center">
      {ASSO['nom']} · RNA {ASSO['rna']}<br>
      {ASSO['siege']}<br>
      <a href="mailto:{ASSO['email']}" style="color:#1a7a4a">{ASSO['email']}</a>
      &nbsp;·&nbsp;
      <a href="{SITE_URL}" style="color:#1a7a4a">{SITE_URL}</a>
    </p>"""

def email_header(titre=None):
    t = titre or ASSO['nom']
    return f"""
    <div style="background:#1a7a4a;padding:24px;text-align:center">
      <h1 style="color:#fff;margin:0;font-size:1.3rem">{ASSO['nom']}</h1>
      <p style="color:rgba(255,255,255,.75);margin:.4rem 0 0;font-size:.85rem">
        Solidarité · Entraide · Développement
      </p>
    </div>"""

# ── GÉNÉRATION CARTE MEMBRE ───────────────────────────────────────────────────

def generate_carte_membre(prenom: str, nom: str, matricule: str) -> bytes:
    """Génère la carte membre en PNG et retourne les bytes."""
    from PIL import Image, ImageDraw, ImageFont

    template_path = os.path.join("static", "img", "carte_template.png")
    if os.path.exists(template_path):
        img = Image.open(template_path).convert("RGBA")
    else:
        img = Image.new("RGBA", (1748, 1240), (245, 247, 250, 255))

    draw = ImageDraw.Draw(img)
    w, h = img.size  # 1748 × 1240

    font_path      = os.path.join("static", "fonts", "Montserrat.ttf")
    font_path_bold = os.path.join("static", "fonts", "Montserrat-Bold.ttf")
    try:
        font_nom = ImageFont.truetype(font_path_bold if os.path.exists(font_path_bold) else font_path,
                                      size=int(h * 0.052))
        font_mat = ImageFont.truetype(font_path_bold if os.path.exists(font_path_bold) else font_path,
                                      size=int(h * 0.032))
    except Exception:
        font_nom = ImageFont.load_default(size=int(h * 0.052))
        font_mat = ImageFont.load_default(size=int(h * 0.032))

    def fill_box_and_write(left_pct, top_pct, right_pct, bot_pct, text):
        """Échantillonne la couleur de la boîte, la remplit entièrement, puis écrit le texte en blanc."""
        x1, y1 = int(w * left_pct),  int(h * top_pct)
        x2, y2 = int(w * right_pct), int(h * bot_pct)
        # Couleur centrale de la boîte (échantillonnée depuis le template)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        box_color = img.getpixel((cx, cy))[:3]
        # Remplissage COMPLET de la boîte (sans marge)
        draw.rectangle([x1, y1, x2, y2], fill=box_color)
        # Texte centré verticalement, indenté horizontalement
        text_x = x1 + int(w * 0.012)
        text_h  = int(h * 0.052)
        text_y  = y1 + (y2 - y1 - text_h) // 2
        draw.text((text_x, text_y), text.upper(), fill="white", font=font_nom)

    # ── Boîte NOM (élargie : 49.8 % → 61.5 % hauteur) ─────────────────────
    fill_box_and_write(0.069, 0.498, 0.505, 0.615, nom)

    # ── Boîte PRENOM (élargie : 62.4 % → 73.8 % hauteur) ────────────────────
    fill_box_and_write(0.069, 0.624, 0.505, 0.738, prenom)

    # ── Matricule (couvrir le texte template puis réécrire) ───────────────────
    mat_x  = int(w * 0.069)
    mat_y  = int(h * 0.833)
    mat_x2 = int(w * 0.430)
    mat_y2 = mat_y + int(h * 0.048)
    # Couleur de fond à cet endroit
    bg_color = img.getpixel((mat_x + 10, mat_y + int(h * 0.020)))[:3]
    draw.rectangle([mat_x, mat_y, mat_x2, mat_y2], fill=bg_color)
    draw.text((mat_x, mat_y), f"N° matricule : {matricule}", fill="#1a3a6b", font=font_mat)

    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()


# ── ROUTES PUBLIQUES ──────────────────────────────────────────────────────────

@app.route("/")
def index():
    total_adhesions = Adhesion.query.count()
    total_dons      = Don.query.count()
    montant_total   = db.session.query(db.func.sum(Don.montant)).scalar() or 0
    stats = [
        {"value": "2026",                   "label": "Année de fondation"},
        {"value": total_adhesions,          "label": "Adhésions récentes"},
        {"value": total_dons,               "label": "Dons reçus"},
        {"value": f"{montant_total:.0f} €", "label": "Montant récemment collecté"},
    ]
    projets    = Projet.query.filter_by(publie=True).order_by(Projet.date_creation.desc()).limit(3).all()
    actualites = Actualite.query.filter_by(publie=True).order_by(Actualite.date_creation.desc()).limit(3).all()
    membres_ca = MembreBureau.query.filter_by(actif=True).order_by(MembreBureau.ordre).all()
    return render_template("index.html", asso=ASSO, stats=stats,
                           membres_ca=membres_ca, projets=projets,
                           actualites=actualites, now=datetime.now())

@app.route("/projets")
def projets():
    projets = Projet.query.filter_by(publie=True).order_by(Projet.date_creation.desc()).all()
    return render_template("projets.html", asso=ASSO, projets=projets, now=datetime.now())

@app.route("/projets/<slug>")
def projet_detail(slug):
    projet = Projet.query.filter_by(slug=slug, publie=True).first_or_404()
    return render_template("projet_detail.html", asso=ASSO, projet=projet, now=datetime.now())

@app.route("/actualites")
def actualites():
    actualites = Actualite.query.filter_by(publie=True).order_by(Actualite.date_creation.desc()).all()
    return render_template("actualites.html", asso=ASSO, actualites=actualites, now=datetime.now())

@app.route("/actualites/<slug>")
def actualite_detail(slug):
    actu = Actualite.query.filter_by(slug=slug, publie=True).first_or_404()
    return render_template("actualite_detail.html", asso=ASSO, actu=actu, now=datetime.now())

@app.route("/presentation")
def presentation():
    membres_ca = MembreBureau.query.filter_by(actif=True).order_by(MembreBureau.ordre).all()
    return render_template("presentation.html", asso=ASSO, membres_ca=membres_ca, now=datetime.now())

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        nom     = request.form.get("nom", "").strip()
        email   = request.form.get("email", "").strip()
        sujet   = request.form.get("sujet", "").strip()
        message = request.form.get("message", "").strip()
        if nom and email and message:
            db.session.add(ContactMessage(nom=nom, email=email, sujet=sujet, message=message))
            db.session.commit()
            msg = MailMessage(subject=f"[AKF] Nouveau message — {sujet or 'Contact'}",
                              recipients=[MAIL_NOTIFICATIONS])
            msg.html = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
              {email_header()}
              <div style="padding:30px;background:#fff">
                <h2 style="color:#1a7a4a;font-size:1rem">Nouveau message depuis le site</h2>
                <table style="width:100%;border-collapse:collapse;font-size:.9rem">
                  <tr><td style="padding:6px 0;color:#6b7280;width:120px">Nom</td><td><strong>{nom}</strong></td></tr>
                  <tr><td style="padding:6px 0;color:#6b7280">Email</td><td><a href="mailto:{email}" style="color:#1a7a4a">{email}</a></td></tr>
                  <tr><td style="padding:6px 0;color:#6b7280">Sujet</td><td>{sujet or '—'}</td></tr>
                </table>
                <div style="background:#f8faf9;border-left:4px solid #1a7a4a;border-radius:4px;padding:16px;margin-top:16px">
                  <p style="margin:0;line-height:1.7">{message.replace(chr(10), '<br>')}</p>
                </div>
                {email_footer()}
              </div>
            </div>"""
            send_mail_safe(msg)
            flash("Votre message a bien été envoyé. Merci !", "success")
            return redirect(url_for("contact"))
        flash("Veuillez remplir tous les champs obligatoires.", "danger")
        return redirect(url_for("contact"))
    return render_template("contact.html", asso=ASSO, now=datetime.now())

@app.route("/adhesion", methods=["GET", "POST"])
def adhesion():
    if request.method == "POST":
        prenom           = request.form.get("prenom", "").strip()
        nom              = request.form.get("nom", "").strip()
        email            = request.form.get("email", "").strip()
        telephone        = request.form.get("telephone", "").strip()
        civilite         = request.form.get("civilite", "").strip()
        date_naissance   = request.form.get("date_naissance", "").strip()
        etudiant         = request.form.get("etudiant", "non")
        etablissement    = request.form.get("etablissement", "").strip()
        profession       = request.form.get("profession", "").strip()
        profession_autre = request.form.get("profession_autre", "").strip()
        adresse          = request.form.get("adresse", "").strip()
        code_postal      = request.form.get("code_postal", "").strip()
        ville            = request.form.get("ville", "").strip()
        pays             = request.form.get("pays", "France")
        type_adhesion    = request.form.get("type_adhesion", "membre_actif")
        motivation       = request.form.get("motivation", "").strip()

        if not (prenom and nom and email):
            flash("Veuillez compléter les champs obligatoires.", "danger")
            return redirect(url_for("adhesion"))

        # Migration préventive : s'assure que les colonnes existent avant l'INSERT
        try:
            from sqlalchemy import text as _text
            with db.engine.connect() as _conn:
                _conn.execute(_text("ALTER TABLE adhesion ADD COLUMN IF NOT EXISTS matricule VARCHAR(20)"))
                _conn.execute(_text("ALTER TABLE adhesion ADD COLUMN IF NOT EXISTS stripe_session_id VARCHAR(255)"))
                _conn.commit()
        except Exception as _me:
            print(f"[adhesion] migration préventive : {_me}", flush=True)

        # Sauvegarde en_attente (avant paiement)
        adh = Adhesion(
            civilite=civilite, prenom=prenom, nom=nom, email=email,
            telephone=telephone, date_naissance=date_naissance,
            etudiant=etudiant, etablissement=etablissement,
            profession=profession, profession_autre=profession_autre,
            adresse=adresse, code_postal=code_postal,
            ville=ville, pays=pays, type_adhesion=type_adhesion,
            motivation=motivation, statut="en_attente"
        )
        db.session.add(adh)
        db.session.commit()

        if not adh.id:
            flash("Erreur lors de la sauvegarde de votre adhésion. Veuillez réessayer.", "danger")
            return redirect(url_for("adhesion"))

        # Détermination du montant Stripe
        if etudiant == "oui":
            montant = ADHESION_PRIX["etudiant"]
            label   = "Adhésion étudiant – AKF"
        elif type_adhesion == "membre_bienfaiteur":
            montant = ADHESION_PRIX["membre_bienfaiteur"]
            label   = "Adhésion membre bienfaiteur – AKF"
        else:
            montant = ADHESION_PRIX["membre_actif"]
            label   = "Adhésion membre actif – AKF"

        try:
            checkout = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "eur",
                        "product_data": {"name": label, "description": f"{prenom} {nom}"},
                        "unit_amount": montant,
                    },
                    "quantity": 1,
                }],
                mode="payment",
                customer_email=email,
                success_url=url_for("adhesion_success", _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=url_for("adhesion_cancel", _external=True),
                metadata={"adhesion_id": str(adh.id)},
            )
            adh.stripe_session_id = checkout.id
            db.session.commit()
            return redirect(checkout.url, code=303)
        except Exception as e:
            print(f"[Stripe] erreur : {e}")
            db.session.delete(adh)
            db.session.commit()
            flash("Erreur lors de la création du paiement. Veuillez réessayer.", "danger")
            return redirect(url_for("adhesion"))

    return render_template("adhesion.html", asso=ASSO, now=datetime.now())


@app.route("/adhesion/success")
def adhesion_success():
    try:
        session_id = request.args.get("session_id", "")
        if not session_id:
            return "<pre>ERREUR: session_id absent de l'URL</pre>", 400

        # Étape 1 — récupération Stripe
        try:
            checkout = stripe.checkout.Session.retrieve(session_id)
        except Exception as e:
            msg = f"Stripe retrieve échoué:\n{e}\n\nClé utilisée: {stripe.api_key[:16]}..."
            print(f"[adhesion/success] {msg}", flush=True)
            return f"<pre style='color:red'>{msg}</pre>", 200

        if checkout.payment_status != "paid":
            return f"<pre>payment_status={checkout.payment_status!r} (attendu: 'paid')</pre>", 200

        # Étape 2 — récupération adhésion
        try:
            # StripeObject v7 ne supporte pas .get() → utiliser ["key"]
            adhesion_id_raw = checkout.metadata["adhesion_id"]
            adhesion_id = int(adhesion_id_raw)
            adh = Adhesion.query.filter_by(id=adhesion_id).first()
        except (KeyError, AttributeError, TypeError) as e:
            return f"<pre style='color:orange'>adhesion_id absent des métadonnées Stripe.\nmetadata={checkout.metadata!r}</pre>", 200
        except Exception as e:
            import traceback
            msg = f"DB lookup échoué: {type(e).__name__}: {e}\n{traceback.format_exc()}"
            print(f"[adhesion/success] {msg}", flush=True)
            return f"<pre style='color:red'>{msg}</pre>", 200

        if not adh:
            return f"<pre>Adhésion id={adhesion_id} introuvable (metadata={dict(checkout.metadata)!r})</pre>", 200

        # Étape 3 — activation
        if adh.statut == "en_attente":
            try:
                adh.statut    = "actif"
                adh.matricule = f"AKF-{adh.id:04d}"
                db.session.commit()
                # Forcer le rechargement après commit (expire_on_commit)
                db.session.refresh(adh)
            except Exception as e:
                db.session.rollback()
                print(f"[adhesion/success] commit: {e}", flush=True)
                try:
                    from sqlalchemy import text
                    with db.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE adhesion ADD COLUMN IF NOT EXISTS matricule VARCHAR(20)"))
                        conn.execute(text("ALTER TABLE adhesion ADD COLUMN IF NOT EXISTS stripe_session_id VARCHAR(255)"))
                        conn.execute(text("UPDATE adhesion SET statut='actif', matricule=:mat WHERE id=:id"),
                                     {"mat": f"AKF-{adh.id:04d}", "id": adh.id})
                        conn.commit()
                    adh = Adhesion.query.filter_by(id=adh.id).first()
                except Exception as e2:
                    print(f"[adhesion/success] fallback SQL: {e2}", flush=True)

            # Envoi carte
            try:
                mat   = adh.matricule or f"AKF-{adh.id:04d}"
                carte = generate_carte_membre(adh.prenom, adh.nom, mat)
                msg_m = MailMessage(subject=f"[AKF] Bienvenue {adh.prenom} ! Votre carte de membre",
                                    recipients=[adh.email])
                msg_m.html = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
                  {email_header()}
                  <div style="padding:30px;background:#fff">
                    <h2 style="color:#1a7a4a">Bienvenue dans l'AKF, {adh.prenom} !</h2>
                    <p>Votre adhésion a été validée. Vous trouverez ci-joint votre carte de membre.</p>
                    <table style="width:100%;border-collapse:collapse;font-size:.9rem;margin:16px 0">
                      <tr><td style="padding:5px 0;color:#6b7280;width:140px">Matricule</td>
                          <td><strong>{mat}</strong></td></tr>
                      <tr><td style="padding:5px 0;color:#6b7280">Nom complet</td>
                          <td>{adh.prenom} {adh.nom}</td></tr>
                      <tr><td style="padding:5px 0;color:#6b7280">Type</td>
                          <td>{adh.type_adhesion}</td></tr>
                    </table>
                    <p style="color:#6b7280;font-size:.85rem">Conservez précieusement votre carte.</p>
                    {email_footer()}
                  </div>
                </div>"""
                msg_m.attach(f"carte_membre_{mat}.png", "image/png", carte)
                notif = MailMessage(subject=f"[AKF] Nouvelle adhésion — {adh.prenom} {adh.nom}",
                                    recipients=[MAIL_NOTIFICATIONS])
                notif.html = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
                  {email_header()}
                  <div style="padding:30px;background:#fff">
                    <p><strong>{adh.prenom} {adh.nom}</strong> a finalisé son adhésion (matricule <strong>{mat}</strong>).</p>
                    {email_footer()}
                  </div>
                </div>"""
                send_mail_safe(msg_m)
                send_mail_safe(notif)
            except Exception as e:
                print(f"[carte/mail] {e}", flush=True)

        # Snapshot des données avant fermeture session
        ctx = {
            "prenom":        adh.prenom,
            "nom":           adh.nom,
            "email":         adh.email,
            "matricule":     adh.matricule or f"AKF-{adh.id:04d}",
            "type_adhesion": adh.type_adhesion,
            "statut":        adh.statut,
        }
        return render_template("adhesion_success.html", asso=ASSO, ctx=ctx, now=datetime.now())

    except Exception as e:
        import traceback
        err = traceback.format_exc()
        print(f"[adhesion/success] EXCEPTION GLOBALE:\n{err}", flush=True)
        return f"<pre style='color:red'>EXCEPTION GLOBALE:\n{err}</pre>", 200


@app.route("/adhesion/cancel")
def adhesion_cancel():
    flash("Paiement annulé. Votre inscription n'a pas été finalisée.", "warning")
    return redirect(url_for("adhesion"))


@app.route("/debug/stripe/<session_id>")
def debug_stripe(session_id):
    """Endpoint temporaire de diagnostic — à supprimer en production."""
    result = {}
    try:
        checkout = stripe.checkout.Session.retrieve(session_id)
        result["payment_status"] = checkout.payment_status
        result["metadata"]       = dict(checkout.metadata._data) if hasattr(checkout.metadata, '_data') else {}
        result["amount_total"]   = checkout.amount_total
        result["stripe_key_prefix"] = stripe.api_key[:12] + "..."

        adhesion_id = int(checkout.metadata["adhesion_id"])
        adh = Adhesion.query.filter_by(id=adhesion_id).first()
        result["adhesion_found"] = adh is not None
        if adh:
            result["adhesion_statut"]   = adh.statut
            result["adhesion_matricule"] = adh.matricule
    except Exception as e:
        result["error"] = str(e)
    return jsonify(result)

@app.route("/don", methods=["GET", "POST"])
def don():
    if request.method == "POST":
        montant  = request.form.get("montant", "25")
        nom      = request.form.get("nom", "").strip()
        email    = request.form.get("email", "").strip()
        devise   = "EUR"
        montant_centimes = int(float(montant) * 100)
        checkout = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            customer_email=email if email else None,
            line_items=[{"price_data": {"currency": devise.lower(),
                          "product_data": {"name": "Don à l'AKF"},
                          "unit_amount": montant_centimes}, "quantity": 1}],
            success_url=url_for("don_success", _external=True),
            cancel_url=url_for("don", _external=True),
        )
        db.session.add(Don(nom=nom, email=email, montant=float(montant),
                           devise=devise, stripe_session_id=checkout.id))
        db.session.commit()
        msg = MailMessage(subject=f"[AKF] Nouveau don — {montant} {devise}",
                          recipients=[MAIL_NOTIFICATIONS])
        msg.body = f"Nom : {nom}\nEmail : {email}\nMontant : {montant} {devise}"
        send_mail_safe(msg)
        return redirect(checkout.url, code=303)
    objectif         = 500
    montant_collecte = db.session.query(db.func.sum(Don.montant)).scalar() or 0
    nb_dons          = Don.query.count()
    pourcentage      = min(int((montant_collecte / objectif) * 100), 100)
    return render_template("don.html", asso=ASSO, now=datetime.now(),
                           objectif=objectif, montant_collecte=montant_collecte,
                           nb_dons=nb_dons, pourcentage=pourcentage)

@app.route("/don/success")
def don_success():
    flash("Merci pour votre don. Votre paiement a bien été pris en compte.", "success")
    return redirect(url_for("index"))

@app.route("/mentions-legales")
def mentions_legales():
    return render_template("mentions_legales.html", asso=ASSO, now=datetime.now())

@app.route("/evenements")
def evenements():
    now     = datetime.now()
    a_venir = Evenement.query.filter(Evenement.publie==True, Evenement.date_event>=now).order_by(Evenement.date_event.asc()).all()
    passes  = Evenement.query.filter(Evenement.publie==True, Evenement.date_event<now).order_by(Evenement.date_event.desc()).limit(6).all()
    return render_template("evenements.html", asso=ASSO, a_venir=a_venir, passes=passes, now=now)

@app.route("/evenements/<slug>")
def evenement_detail(slug):
    evt    = Evenement.query.filter_by(slug=slug, publie=True).first_or_404()
    autres = Evenement.query.filter(Evenement.publie==True, Evenement.id!=evt.id,
                                    Evenement.date_event>=datetime.now()).order_by(Evenement.date_event.asc()).limit(3).all()
    return render_template("evenement_detail.html", asso=ASSO, evt=evt, autres=autres, now=datetime.now())

@app.route("/api/projets")
def api_projets():
    return jsonify([{"id": p.id, "titre": p.titre, "slug": p.slug} for p in Projet.query.filter_by(publie=True).all()])

@app.route("/api/actualites")
def api_actualites():
    return jsonify([{"id": a.id, "titre": a.titre, "slug": a.slug} for a in Actualite.query.filter_by(publie=True).all()])

# ── ADMIN AUTH ────────────────────────────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin    = AdminUser.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            session["admin_logged_in"] = True
            session["admin_username"]  = username
            return redirect(url_for("admin_dashboard"))
        flash("Identifiants incorrects.", "danger")
    return render_template("admin/login.html", asso=ASSO, now=datetime.now())

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

# ── ADMIN PARAMÈTRES ──────────────────────────────────────────────────────────

@app.route("/admin/parametres", methods=["GET", "POST"])
@login_required
def admin_parametres():
    admin       = AdminUser.query.filter_by(username=session.get("admin_username")).first_or_404()
    tous_admins = AdminUser.query.all()
    return render_template("admin/parametres.html", asso=ASSO, admin=admin,
                           tous_admins=tous_admins, now=datetime.now())

@app.route("/admin/parametres/mot-de-passe", methods=["POST"])
@login_required
def admin_changer_mdp():
    admin   = AdminUser.query.filter_by(username=session.get("admin_username")).first_or_404()
    actuel  = request.form.get("actuel", "")
    nouveau = request.form.get("nouveau", "")
    confirm = request.form.get("confirm", "")
    if not admin.check_password(actuel): flash("Mot de passe actuel incorrect.", "danger")
    elif len(nouveau) < 6: flash("Le nouveau mot de passe doit faire au moins 6 caractères.", "danger")
    elif nouveau != confirm: flash("Les deux mots de passe ne correspondent pas.", "danger")
    else:
        admin.set_password(nouveau); db.session.commit()
        flash("Mot de passe modifié avec succès.", "success")
    return redirect(url_for("admin_parametres"))

@app.route("/admin/parametres/ajouter-admin", methods=["POST"])
@login_required
def admin_ajouter_admin():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    confirm  = request.form.get("confirm", "")
    if not username or not password: flash("Identifiant et mot de passe obligatoires.", "danger")
    elif password != confirm: flash("Les mots de passe ne correspondent pas.", "danger")
    elif AdminUser.query.filter_by(username=username).first(): flash(f"L'identifiant '{username}' existe déjà.", "danger")
    elif len(password) < 6: flash("Le mot de passe doit faire au moins 6 caractères.", "danger")
    else:
        a = AdminUser(username=username); a.set_password(password)
        db.session.add(a); db.session.commit()
        flash(f"Compte admin '{username}' créé.", "success")
    return redirect(url_for("admin_parametres"))

@app.route("/admin/parametres/supprimer-admin/<int:id>")
@login_required
def admin_supprimer_admin(id):
    a = AdminUser.query.get_or_404(id)
    if a.username == session.get("admin_username"):
        flash("Vous ne pouvez pas supprimer votre propre compte.", "danger")
    elif AdminUser.query.count() <= 1:
        flash("Impossible de supprimer le dernier compte administrateur.", "danger")
    else:
        db.session.delete(a); db.session.commit()
        flash(f"Compte '{a.username}' supprimé.", "success")
    return redirect(url_for("admin_parametres"))

# ── ADMIN DASHBOARD ───────────────────────────────────────────────────────────

@app.route("/admin")
@login_required
def admin_dashboard():
    stats = {
        "membres":     Adhesion.query.count(),
        "en_attente":  Adhesion.query.filter_by(statut="en_attente").count(),
        "dons":        Don.query.count(),
        "total_dons":  db.session.query(db.func.sum(Don.montant)).scalar() or 0,
        "messages":    ContactMessage.query.count(),
        "non_lus":     ContactMessage.query.filter_by(lu=False).count(),
        "projets":     Projet.query.count(),
        "actualites":  Actualite.query.count(),
        "bureau":      MembreBureau.query.count(),
        "cot_payes":   Cotisation.query.filter_by(mois=datetime.now().month, annee=datetime.now().year, statut="paye").count(),
        "cot_attente": Cotisation.query.filter_by(mois=datetime.now().month, annee=datetime.now().year, statut="en_attente").count(),
    }
    return render_template("admin/dashboard.html", asso=ASSO, stats=stats, now=datetime.now())

# ── ADMIN PROJETS ─────────────────────────────────────────────────────────────

@app.route("/admin/projets")
@login_required
def admin_projets():
    return render_template("admin/projets.html", asso=ASSO,
                           projets=Projet.query.order_by(Projet.date_creation.desc()).all(), now=datetime.now())

@app.route("/admin/projets/nouveau", methods=["GET", "POST"])
@login_required
def admin_projet_nouveau():
    if request.method == "POST":
        titre = request.form.get("titre", "").strip()
        slug  = make_slug(titre); base, i = slug, 1
        while Projet.query.filter_by(slug=slug).first(): slug = f"{base}-{i}"; i += 1
        db.session.add(Projet(titre=titre, categorie=request.form.get("categorie","").strip(),
                              description=request.form.get("description","").strip(),
                              contenu=request.form.get("contenu","").strip(),
                              slug=slug, image=save_upload(request.files.get("image")),
                              publie=request.form.get("publie")=="on"))
        db.session.commit(); flash("Projet créé avec succès.", "success")
        return redirect(url_for("admin_projets"))
    return render_template("admin/projet_form.html", asso=ASSO, projet=None, now=datetime.now())

@app.route("/admin/projets/<int:id>/modifier", methods=["GET", "POST"])
@login_required
def admin_projet_modifier(id):
    projet = Projet.query.get_or_404(id)
    if request.method == "POST":
        projet.titre       = request.form.get("titre","").strip()
        projet.categorie   = request.form.get("categorie","").strip()
        projet.description = request.form.get("description","").strip()
        projet.contenu     = request.form.get("contenu","").strip()
        projet.publie      = request.form.get("publie") == "on"
        ni = save_upload(request.files.get("image"))
        if ni: projet.image = ni
        db.session.commit(); flash("Projet mis à jour.", "success")
        return redirect(url_for("admin_projets"))
    return render_template("admin/projet_form.html", asso=ASSO, projet=projet, now=datetime.now())

@app.route("/admin/projets/<int:id>/supprimer")
@login_required
def admin_projet_supprimer(id):
    p = Projet.query.get_or_404(id); db.session.delete(p); db.session.commit()
    flash("Projet supprimé.", "success"); return redirect(url_for("admin_projets"))

# ── ADMIN ACTUALITÉS ──────────────────────────────────────────────────────────

@app.route("/admin/actualites")
@login_required
def admin_actualites():
    return render_template("admin/actualites.html", asso=ASSO,
                           actualites=Actualite.query.order_by(Actualite.date_creation.desc()).all(), now=datetime.now())

@app.route("/admin/actualites/nouvelle", methods=["GET", "POST"])
@login_required
def admin_actualite_nouvelle():
    if request.method == "POST":
        titre = request.form.get("titre","").strip()
        slug  = make_slug(titre); base, i = slug, 1
        while Actualite.query.filter_by(slug=slug).first(): slug = f"{base}-{i}"; i += 1
        db.session.add(Actualite(titre=titre, categorie=request.form.get("categorie","").strip(),
                                  extrait=request.form.get("extrait","").strip(),
                                  contenu=request.form.get("contenu","").strip(),
                                  slug=slug, image=save_upload(request.files.get("image")),
                                  publie=request.form.get("publie")=="on"))
        db.session.commit(); flash("Actualité créée avec succès.", "success")
        return redirect(url_for("admin_actualites"))
    return render_template("admin/actualite_form.html", asso=ASSO, actu=None, now=datetime.now())

@app.route("/admin/actualites/<int:id>/modifier", methods=["GET", "POST"])
@login_required
def admin_actualite_modifier(id):
    actu = Actualite.query.get_or_404(id)
    if request.method == "POST":
        actu.titre     = request.form.get("titre","").strip()
        actu.categorie = request.form.get("categorie","").strip()
        actu.extrait   = request.form.get("extrait","").strip()
        actu.contenu   = request.form.get("contenu","").strip()
        actu.publie    = request.form.get("publie") == "on"
        ni = save_upload(request.files.get("image"))
        if ni: actu.image = ni
        db.session.commit(); flash("Actualité mise à jour.", "success")
        return redirect(url_for("admin_actualites"))
    return render_template("admin/actualite_form.html", asso=ASSO, actu=actu, now=datetime.now())

@app.route("/admin/actualites/<int:id>/supprimer")
@login_required
def admin_actualite_supprimer(id):
    a = Actualite.query.get_or_404(id); db.session.delete(a); db.session.commit()
    flash("Actualité supprimée.", "success"); return redirect(url_for("admin_actualites"))

# ── ADMIN BUREAU ──────────────────────────────────────────────────────────────

@app.route("/admin/bureau")
@login_required
def admin_bureau():
    return render_template("admin/bureau.html", asso=ASSO,
                           membres=MembreBureau.query.order_by(MembreBureau.ordre).all(), now=datetime.now())

@app.route("/admin/bureau/nouveau", methods=["GET", "POST"])
@login_required
def admin_bureau_nouveau():
    if request.method == "POST":
        db.session.add(MembreBureau(nom=request.form.get("nom","").strip(),
                                     poste=request.form.get("poste","").strip(),
                                     ordre=int(request.form.get("ordre",0)),
                                     actif=request.form.get("actif")=="on",
                                     photo=save_upload(request.files.get("photo"))))
        db.session.commit(); flash("Membre ajouté.", "success")
        return redirect(url_for("admin_bureau"))
    return render_template("admin/bureau_form.html", asso=ASSO, membre=None, now=datetime.now())

@app.route("/admin/bureau/<int:id>/modifier", methods=["GET", "POST"])
@login_required
def admin_bureau_modifier(id):
    m = MembreBureau.query.get_or_404(id)
    if request.method == "POST":
        m.nom = request.form.get("nom","").strip(); m.poste = request.form.get("poste","").strip()
        m.ordre = int(request.form.get("ordre",0)); m.actif = request.form.get("actif")=="on"
        np = save_upload(request.files.get("photo"))
        if np: m.photo = np
        db.session.commit(); flash("Membre mis à jour.", "success")
        return redirect(url_for("admin_bureau"))
    return render_template("admin/bureau_form.html", asso=ASSO, membre=m, now=datetime.now())

@app.route("/admin/bureau/<int:id>/supprimer")
@login_required
def admin_bureau_supprimer(id):
    m = MembreBureau.query.get_or_404(id); db.session.delete(m); db.session.commit()
    flash("Membre supprimé.", "success"); return redirect(url_for("admin_bureau"))

# ── ADMIN ADHÉSIONS ───────────────────────────────────────────────────────────

@app.route("/admin/adhesions")
@login_required
def admin_adhesions():
    return render_template("admin/adhesions.html", asso=ASSO,
                           adhesions=Adhesion.query.order_by(Adhesion.date_creation.desc()).all(), now=datetime.now())

@app.route("/admin/adhesions/<int:id>/statut/<statut>")
@login_required
def admin_adhesion_statut(id, statut):
    a = Adhesion.query.get_or_404(id)
    if statut in ["actif","inactif","en_attente"]:
        a.statut = statut; db.session.commit(); flash("Statut mis à jour.", "success")
    return redirect(url_for("admin_adhesions"))

@app.route("/admin/adhesions/<int:id>/supprimer")
@login_required
def admin_adhesion_supprimer(id):
    a = Adhesion.query.get_or_404(id); db.session.delete(a); db.session.commit()
    flash("Adhésion supprimée.", "success"); return redirect(url_for("admin_adhesions"))

# ── ADMIN DONS ────────────────────────────────────────────────────────────────

@app.route("/admin/dons")
@login_required
def admin_dons():
    dons  = Don.query.order_by(Don.date_creation.desc()).all()
    total = db.session.query(db.func.sum(Don.montant)).scalar() or 0
    return render_template("admin/dons.html", asso=ASSO, dons=dons, total=total, now=datetime.now())

# ── ADMIN MESSAGES ────────────────────────────────────────────────────────────

@app.route("/admin/messages")
@login_required
def admin_messages():
    return render_template("admin/messages.html", asso=ASSO,
                           messages=ContactMessage.query.order_by(ContactMessage.date_creation.desc()).all(), now=datetime.now())

@app.route("/admin/messages/<int:id>")
@login_required
def admin_message_detail(id):
    msg = ContactMessage.query.get_or_404(id); msg.lu = True; db.session.commit()
    return render_template("admin/message_detail.html", asso=ASSO, msg=msg, now=datetime.now())

@app.route("/admin/messages/<int:id>/supprimer")
@login_required
def admin_message_supprimer(id):
    msg = ContactMessage.query.get_or_404(id); db.session.delete(msg); db.session.commit()
    flash("Message supprimé.", "success"); return redirect(url_for("admin_messages"))

# ── ADMIN ÉVÉNEMENTS ──────────────────────────────────────────────────────────

@app.route("/admin/evenements")
@login_required
def admin_evenements():
    return render_template("admin/evenements.html", asso=ASSO,
                           evenements=Evenement.query.order_by(Evenement.date_event.desc()).all(), now=datetime.now())

@app.route("/admin/evenements/nouveau", methods=["GET", "POST"])
@login_required
def admin_evenement_nouveau():
    if request.method == "POST":
        titre = request.form.get("titre","").strip()
        try: date_event = datetime.strptime(request.form.get("date_event",""), "%Y-%m-%dT%H:%M")
        except: flash("Format de date invalide.", "danger"); return redirect(url_for("admin_evenement_nouveau"))
        slug = make_slug(titre); base, i = slug, 1
        while Evenement.query.filter_by(slug=slug).first(): slug = f"{base}-{i}"; i += 1
        db.session.add(Evenement(titre=titre, type_event=request.form.get("type_event",""),
                                  description=request.form.get("description","").strip(),
                                  lieu=request.form.get("lieu","").strip(),
                                  adresse=request.form.get("adresse","").strip(),
                                  date_event=date_event, heure_fin=request.form.get("heure_fin","").strip(),
                                  lien_externe=request.form.get("lien_externe","").strip(),
                                  image=save_upload(request.files.get("image")),
                                  publie=request.form.get("publie")=="on", slug=slug))
        db.session.commit(); flash("Événement créé avec succès.", "success")
        return redirect(url_for("admin_evenements"))
    return render_template("admin/evenement_form.html", asso=ASSO, evt=None, now=datetime.now())

@app.route("/admin/evenements/<int:id>/modifier", methods=["GET", "POST"])
@login_required
def admin_evenement_modifier(id):
    evt = Evenement.query.get_or_404(id)
    if request.method == "POST":
        evt.titre=request.form.get("titre","").strip(); evt.type_event=request.form.get("type_event","")
        evt.description=request.form.get("description","").strip(); evt.lieu=request.form.get("lieu","").strip()
        evt.adresse=request.form.get("adresse","").strip(); evt.heure_fin=request.form.get("heure_fin","").strip()
        evt.lien_externe=request.form.get("lien_externe","").strip(); evt.publie=request.form.get("publie")=="on"
        try: evt.date_event = datetime.strptime(request.form.get("date_event",""), "%Y-%m-%dT%H:%M")
        except: pass
        ni = save_upload(request.files.get("image"))
        if ni: evt.image = ni
        db.session.commit(); flash("Événement mis à jour.", "success")
        return redirect(url_for("admin_evenements"))
    return render_template("admin/evenement_form.html", asso=ASSO, evt=evt, now=datetime.now())

@app.route("/admin/evenements/<int:id>/supprimer")
@login_required
def admin_evenement_supprimer(id):
    e = Evenement.query.get_or_404(id); db.session.delete(e); db.session.commit()
    flash("Événement supprimé.", "success"); return redirect(url_for("admin_evenements"))

# ── ADMIN ENVOYER EMAIL ───────────────────────────────────────────────────────

@app.route("/admin/envoyer-email", methods=["GET", "POST"])
@login_required
def admin_envoyer_email():
    membres = Adhesion.query.filter_by(statut="actif").order_by(Adhesion.nom).all()
    villes  = sorted(set(m.ville for m in membres if m.ville))

    if request.method == "POST":
        sujet             = request.form.get("sujet","").strip()
        corps             = request.form.get("corps","").strip()
        destinataires_ids = request.form.get("destinataires_ids","")
        piece_jointe      = request.files.get("piece_jointe")

        if not sujet or not corps:
            flash("Le sujet et le message sont obligatoires.", "danger")
            return redirect(url_for("admin_envoyer_email"))

        ids = [int(i) for i in destinataires_ids.split(",") if i.strip().isdigit()]
        if not ids:
            flash("Veuillez sélectionner au moins un destinataire.", "danger")
            return redirect(url_for("admin_envoyer_email"))

        destinataires = [a for a in Adhesion.query.filter(Adhesion.id.in_(ids)).all() if a.email]
        if not destinataires:
            flash("Aucun destinataire valide trouvé.", "danger")
            return redirect(url_for("admin_envoyer_email"))

        pj_data = pj_nom = None
        if piece_jointe and piece_jointe.filename:
            pj_data = piece_jointe.read(); pj_nom = piece_jointe.filename

        envoyes = erreurs = 0
        for a in destinataires:
            try:
                msg = MailMessage(subject=sujet, recipients=[a.email],
                    html=f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
                      {email_header()}
                      <div style="padding:30px;background:#fff">
                        <p style="color:#374151;font-size:.95rem;margin-bottom:1rem">
                          Bonjour <strong>{a.prenom} {a.nom}</strong>,
                        </p>
                        <div style="color:#4b5563;line-height:1.8;font-size:.92rem">
                          {corps.replace(chr(10), '<br>')}
                        </div>
                        {email_footer()}
                      </div>
                    </div>""")
                if pj_data and pj_nom: msg.attach(pj_nom, "application/octet-stream", pj_data)
                mail.send(msg); envoyes += 1
            except (Exception, SystemExit, BaseException): erreurs += 1

        if envoyes > 0:
            flash(f"Email envoyé à {envoyes} membre(s)." + (f" {erreurs} échec(s)." if erreurs else ""), "success")
        else:
            flash("Échec de l'envoi. Vérifiez la configuration email.", "danger")
        return redirect(url_for("admin_envoyer_email"))

    return render_template("admin/envoyer_email.html", asso=ASSO, membres=membres, villes=villes, now=datetime.now())

# ── ADMIN COTISATIONS ─────────────────────────────────────────────────────────

MONTANT_ETUDIANT     = 5.0
MONTANT_NON_ETUDIANT = 10.0

def montant_cotisation(adhesion):
    return MONTANT_ETUDIANT if adhesion.etudiant == "oui" else MONTANT_NON_ETUDIANT

def generer_cotisations_mois(mois, annee):
    membres = Adhesion.query.filter_by(statut="actif").all(); crees = 0
    for m in membres:
        if not Cotisation.query.filter_by(adhesion_id=m.id, mois=mois, annee=annee).first():
            db.session.add(Cotisation(adhesion_id=m.id, mois=mois, annee=annee,
                                      montant=montant_cotisation(m), statut="en_attente")); crees += 1
    db.session.commit(); return crees

@app.route("/admin/cotisations")
@login_required
def admin_cotisations():
    now   = datetime.now()
    mois  = int(request.args.get("mois",  now.month))
    annee = int(request.args.get("annee", now.year))
    generer_cotisations_mois(mois, annee)
    cotisations     = Cotisation.query.filter_by(mois=mois, annee=annee).join(Adhesion).order_by(Adhesion.nom).all()
    total_membres   = len(cotisations)
    total_payes     = sum(1 for c in cotisations if c.statut == "paye")
    total_attente   = sum(1 for c in cotisations if c.statut == "en_attente")
    total_retard    = sum(1 for c in cotisations if c.statut == "retard")
    montant_percu   = sum(c.montant for c in cotisations if c.statut == "paye")
    montant_attendu = sum(c.montant for c in cotisations)
    mois_prec, annee_prec = (12, annee-1) if mois == 1  else (mois-1, annee)
    mois_suiv, annee_suiv = (1,  annee+1) if mois == 12 else (mois+1, annee)
    mois_fr = ["","Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
    return render_template("admin/cotisations.html",
        asso=ASSO, cotisations=cotisations, mois=mois, annee=annee, mois_label=mois_fr[mois],
        mois_prec=mois_prec, annee_prec=annee_prec, mois_suiv=mois_suiv, annee_suiv=annee_suiv,
        total_membres=total_membres, total_payes=total_payes, total_attente=total_attente,
        total_retard=total_retard, montant_percu=montant_percu, montant_attendu=montant_attendu,
        membres_non_inclus=[a for a in Adhesion.query.filter_by(statut="actif").all()
                            if not Cotisation.query.filter_by(adhesion_id=a.id, mois=mois, annee=annee).first()],
        now=now)

@app.route("/admin/cotisations/<int:id>/marquer/<statut>")
@login_required
def admin_cotisation_statut(id, statut):
    cot = Cotisation.query.get_or_404(id)
    if statut in ["paye","en_attente","retard","rejete"]:
        cot.statut = statut
        if statut == "paye": cot.date_paiement = datetime.now(); cot.mode_paiement = request.args.get("mode","non précisé")
        db.session.commit(); flash(f"Cotisation de {cot.adhesion.prenom} {cot.adhesion.nom} → {statut}.", "success")
    return redirect(url_for("admin_cotisations", mois=cot.mois, annee=cot.annee))

@app.route("/admin/cotisations/<int:id>/justificatif", methods=["POST"])
@login_required
def admin_cotisation_justificatif(id):
    cot = Cotisation.query.get_or_404(id); f = request.files.get("justificatif")
    if f and f.filename:
        ext = f.filename.rsplit(".",1)[-1].lower(); nom = f"justif_{cot.id}_{cot.mois}_{cot.annee}.{ext}"
        f.save(os.path.join(app.config["UPLOAD_FOLDER"], nom)); cot.justificatif = nom
        db.session.commit(); flash("Justificatif enregistré.", "success")
    return redirect(url_for("admin_cotisations", mois=cot.mois, annee=cot.annee))

@app.route("/admin/cotisations/marquer-retard")
@login_required
def admin_cotisations_marquer_retard():
    now = datetime.now(); mois = int(request.args.get("mois", now.month)); annee = int(request.args.get("annee", now.year))
    from datetime import date
    if date.today() > date(annee, mois, 10):
        nb = Cotisation.query.filter_by(mois=mois, annee=annee, statut="en_attente").update({"statut":"retard"})
        db.session.commit(); flash(f"{nb} cotisation(s) marquée(s) en retard.", "warning")
    else: flash("La date d'échéance (le 10) n'est pas encore passée.", "info")
    return redirect(url_for("admin_cotisations", mois=mois, annee=annee))

def _envoyer_rappel(cot, numero, label):
    try:
        sujets = {1: f"[AKF] Rappel cotisation – {label}", 2: f"[AKF] 2ème rappel – {label}", 3: f"[AKF] Alerte retard – {label}"}
        intro  = {1: "Nous vous rappelons que votre cotisation du mois de",
                  2: "Malgré notre premier rappel, votre cotisation du mois de",
                  3: "Votre cotisation du mois de"}
        fin    = {1: "Merci de régulariser votre situation dans les meilleurs délais.",
                  2: "Nous vous invitons à régulariser d'urgence votre situation.",
                  3: "est désormais en retard. Veuillez contacter le bureau immédiatement."}
        msg = MailMessage(subject=sujets[numero], recipients=[cot.adhesion.email])
        msg.html = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
          {email_header()}
          <div style="padding:30px;background:#fff">
            <p>Bonjour <strong>{cot.adhesion.prenom} {cot.adhesion.nom}</strong>,</p>
            <p>{intro[numero]} <strong>{label}</strong> n'a pas encore été enregistrée.</p>
            <div style="background:#f8faf9;border-left:4px solid #1a7a4a;padding:16px;margin:20px 0;border-radius:4px">
              <p style="margin:0"><strong>Montant :</strong> {cot.montant:.0f} €</p>
              <p style="margin:6px 0 0"><strong>Mois :</strong> {label}</p>
            </div>
            <p>{fin[numero]}</p>
            <ul style="color:#555;line-height:1.8"><li>Virement bancaire</li><li>Wave / PayPal</li><li>Espèces lors d'une réunion</li></ul>
            {email_footer()}
          </div>
        </div>"""
        mail.send(msg); return True
    except (Exception, SystemExit, BaseException) as e:
        print(f"Erreur rappel {cot.adhesion.email}: {e}"); return False

@app.route("/admin/cotisations/rappel/<int:numero>")
@login_required
def admin_cotisations_rappel(numero):
    now = datetime.now(); mois = int(request.args.get("mois", now.month)); annee = int(request.args.get("annee", now.year))
    mois_fr = ["","Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
    label = f"{mois_fr[mois]} {annee}"
    champ = {1:"rappel1_envoye", 2:"rappel2_envoye", 3:"alerte_envoye"}
    filtr = {1:["en_attente"], 2:["en_attente","retard"], 3:["retard"]}
    cots  = Cotisation.query.filter(Cotisation.mois==mois, Cotisation.annee==annee, Cotisation.statut.in_(filtr[numero])).all()
    envoyes = ignores = 0
    for cot in cots:
        if not cot.adhesion.email: continue
        if getattr(cot, champ[numero]): ignores += 1; continue
        if _envoyer_rappel(cot, numero, label):
            setattr(cot, champ[numero], True)
            if numero == 3: cot.statut = "retard"
            envoyes += 1
    db.session.commit()
    noms = {1:"1er rappel", 2:"2ème rappel", 3:"alerte retard"}
    flash(f"{noms[numero]} : {envoyes} email(s) envoyé(s). {ignores} déjà envoyé(s).", "success")
    return redirect(url_for("admin_cotisations", mois=mois, annee=annee))

@app.route("/admin/cotisations/relancer")
@login_required
def admin_cotisations_relancer():
    mois = int(request.args.get("mois", datetime.now().month)); annee = int(request.args.get("annee", datetime.now().year))
    mois_fr = ["","Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
    label = f"{mois_fr[mois]} {annee}"
    en_attente = Cotisation.query.filter(Cotisation.mois==mois, Cotisation.annee==annee,
                                          Cotisation.statut.in_(["en_attente","retard"])).all()
    envoyes = 0
    for cot in en_attente:
        if not cot.adhesion.email: continue
        try:
            statut_txt = "en retard" if cot.statut == "retard" else "à régler"
            msg = MailMessage(subject=f"[AKF] Rappel cotisation – {label}", recipients=[cot.adhesion.email])
            msg.html = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
              {email_header()}
              <div style="padding:30px;background:#fff">
                <p>Bonjour <strong>{cot.adhesion.prenom} {cot.adhesion.nom}</strong>,</p>
                <p>Votre cotisation de <strong>{label}</strong> est <strong>{statut_txt}</strong>.</p>
                <div style="background:#f8faf9;border-radius:8px;padding:20px;margin:20px 0;border-left:4px solid #1a7a4a">
                  <p style="margin:0"><strong>Montant :</strong> {cot.montant:.0f} € / mois</p>
                </div>
                {email_footer()}
              </div>
            </div>"""
            mail.send(msg); envoyes += 1
        except (Exception, SystemExit, BaseException): pass
    flash(f"{envoyes} email(s) de rappel envoyé(s) pour {label}.", "success")
    return redirect(url_for("admin_cotisations", mois=mois, annee=annee))

@app.route("/admin/cotisations/ajouter/<int:mois>/<int:annee>", methods=["POST"])
@login_required
def admin_cotisation_ajouter(mois, annee):
    aid = request.form.get("adhesion_id"); montant = float(request.form.get("montant", 10))
    if aid:
        if not Cotisation.query.filter_by(adhesion_id=aid, mois=mois, annee=annee).first():
            db.session.add(Cotisation(adhesion_id=int(aid), mois=mois, annee=annee, montant=montant, statut="en_attente"))
            db.session.commit(); flash("Membre ajouté aux cotisations du mois.", "success")
        else: flash("Ce membre est déjà inclus dans ce mois.", "danger")
    return redirect(url_for("admin_cotisations", mois=mois, annee=annee))

@app.route("/admin/cotisations/action-groupe/<int:mois>/<int:annee>")
@login_required
def admin_cotisations_action_groupe(mois, annee):
    ids_str = request.args.get("ids",""); statut = request.args.get("statut","en_attente")
    if ids_str and statut in ["paye","en_attente","retard"]:
        for cot_id in [int(i) for i in ids_str.split(",") if i.isdigit()]:
            cot = Cotisation.query.get(cot_id)
            if cot:
                cot.statut = statut
                if statut == "paye": cot.date_paiement = datetime.now(); cot.mode_paiement = "Action groupée"
        db.session.commit(); flash(f"Cotisations mises à jour en '{statut}'.", "success")
    return redirect(url_for("admin_cotisations", mois=mois, annee=annee))

@app.route("/admin/cotisations/email-cible/<int:mois>/<int:annee>", methods=["POST"])
@login_required
def admin_cotisations_email_cible(mois, annee):
    cible = request.form.get("cible","tous"); sujet = request.form.get("sujet","").strip(); corps = request.form.get("corps","").strip()
    mois_fr = ["","Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
    label = f"{mois_fr[mois]} {annee}"; query = Cotisation.query.filter_by(mois=mois, annee=annee)
    if cible == "en_attente": query = query.filter_by(statut="en_attente")
    elif cible == "retard": query = query.filter_by(statut="retard")
    elif cible == "non_payes": query = query.filter(Cotisation.statut.in_(["en_attente","retard"]))
    envoyes = 0
    for cot in query.all():
        if not cot.adhesion.email: continue
        try:
            msg = MailMessage(subject=sujet, recipients=[cot.adhesion.email])
            msg.html = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
              {email_header(f"AKF – Cotisations {label}")}
              <div style="padding:30px;background:#fff">
                <p>Bonjour <strong>{cot.adhesion.prenom} {cot.adhesion.nom}</strong>,</p>
                <div style="line-height:1.7">{corps.replace(chr(10),'<br>')}</div>
                {email_footer()}
              </div>
            </div>"""
            mail.send(msg); envoyes += 1
        except (Exception, SystemExit, BaseException): pass
    flash(f"{envoyes} email(s) envoyé(s).", "success")
    return redirect(url_for("admin_cotisations", mois=mois, annee=annee))

@app.route("/admin/cotisations/email-selection/<int:mois>/<int:annee>", methods=["POST"])
@login_required
def admin_cotisations_email_selection(mois, annee):
    ids_str = request.form.get("ids",""); sujet = request.form.get("sujet","").strip(); corps = request.form.get("corps","").strip()
    if not ids_str: flash("Aucun membre sélectionné.", "danger"); return redirect(url_for("admin_cotisations", mois=mois, annee=annee))
    envoyes = 0
    for cot_id in [int(i) for i in ids_str.split(",") if i.isdigit()]:
        cot = Cotisation.query.get(cot_id)
        if not cot or not cot.adhesion.email: continue
        try:
            msg = MailMessage(subject=sujet, recipients=[cot.adhesion.email])
            msg.html = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
              {email_header()}
              <div style="padding:30px;background:#fff">
                <p>Bonjour <strong>{cot.adhesion.prenom} {cot.adhesion.nom}</strong>,</p>
                <div style="line-height:1.7">{corps.replace(chr(10),'<br>')}</div>
                {email_footer()}
              </div>
            </div>"""
            mail.send(msg); envoyes += 1
        except (Exception, SystemExit, BaseException): pass
    flash(f"{envoyes} email(s) envoyé(s) aux membres sélectionnés.", "success")
    return redirect(url_for("admin_cotisations", mois=mois, annee=annee))

# ── INIT DB ───────────────────────────────────────────────────────────────────

def seed_db():
    """Peuplement initial — ne s'exécute qu'une seule fois (quand admin absent)."""
    a = AdminUser(username="admin"); a.set_password("akf2026")
    db.session.add(a); db.session.commit()

    if MembreBureau.query.count() == 0:
        for nom, poste, photo, ordre in [
            ("Mamadou Moustapha Mané","Président","mane.jpg",0),
            ("Pape Semou NDAO","Secrétaire Général","pape.jpg",1),
            ("Cheikh Willane","Chargé des projets","cheikh.jpg",2),
            ("Idrissa NDAO","Trésorier","idrissa.jpg",3),
            ("Ndeye Awa SY","Trésorière","awa.jpg",4),
            ("Ngoye Mboup","Partenariats","ngoye.jpg",5),
            ("Yangué Barro","Communication","yangue.jpg",6),
            ("Aliou Sow","Communication","aliou.jpg",7),
        ]:
            db.session.add(MembreBureau(nom=nom, poste=poste, photo=photo, ordre=ordre))
        db.session.commit()

    if Projet.query.count() == 0:
        for t,c,d,s in [
            ("Soutien à l'éducation à Koungheul","ÉDUCATION","Accompagner les élèves de Koungheul pour une rentrée scolaire digne.","soutien-education-koungheul"),
            ("Aide sanitaire et médicale","SANTÉ","Financement de consultations médicales.","aide-sanitaire-medicale"),
            ("Développement économique local","ÉCONOMIQUE","Soutenir les initiatives locales, l'artisanat et l'agriculture.","developpement-economique-local"),
            ("Solidarité et cohésion sociale","SOCIALE","Renforcer les liens entre la diaspora et Koungheul.","solidarite-cohesion-sociale"),
        ]:
            db.session.add(Projet(titre=t, categorie=c, description=d, slug=s))
        db.session.commit()

    if Actualite.query.count() == 0:
        for t,c,e,s in [
            ("Création officielle de l'association","Événements","L'AKF a été officiellement créée lors d'une réunion fondatrice à Limoges.","creation-officielle-association"),
            ("Publication au Journal Officiel","Administratif","Déclaration publiée au Journal Officiel (annonce n°2578 du 28 avril 2026).","publication-journal-officiel"),
            ("Lancement de nos premiers projets","Projets","Le bureau se mobilise pour préparer les premiers projets concrets.","lancement-premiers-projets"),
        ]:
            db.session.add(Actualite(titre=t, categorie=c, extrait=e, slug=s))
        db.session.commit()

    if Adhesion.query.count() == 0:
        try:
            import pandas as pd
            f = "Formulaire_sans_titdatare__réponses___1_.xlsx"
            if os.path.exists(f):
                df = pd.read_excel(f); importes = 0
                for _, row in df.iterrows():
                    nc = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
                    vl = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
                    tl = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""
                    em = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else ""
                    sx = str(row.iloc[6]).strip() if pd.notna(row.iloc[6]) else ""
                    mo = str(row.iloc[8]).strip() if pd.notna(row.iloc[8]) else ""
                    if not em or em == "nan": continue
                    if Adhesion.query.filter_by(email=em).first(): continue
                    parts = nc.split(); pr = parts[0] if parts else nc; no = " ".join(parts[1:]) if len(parts) >= 2 else ""
                    try:
                        if 'E' in tl.upper(): tl = str(int(float(tl)))
                    except: pass
                    cv = "Mme" if "femme" in sx.lower() or "féminin" in sx.lower() else "M."
                    db.session.add(Adhesion(civilite=cv, prenom=pr or nc, nom=no, email=em,
                                             telephone=tl[:50], ville=vl, pays="France",
                                             type_adhesion="membre_actif",
                                             motivation=mo[:2000] if mo and mo != "nan" else "",
                                             statut="actif"))
                    importes += 1
                db.session.commit(); print(f"✅ {importes} adhérents importés")
        except Exception as e:
            print(f"⚠️ Import Excel : {e}")


def init_db():
    with app.app_context():
        db.create_all()
        # Migration : ajout des nouvelles colonnes si absentes (PostgreSQL)
        try:
            from sqlalchemy import text
            with db.engine.connect() as conn:
                for sql in [
                    "ALTER TABLE adhesion ADD COLUMN IF NOT EXISTS matricule VARCHAR(20)",
                    "ALTER TABLE adhesion ADD COLUMN IF NOT EXISTS stripe_session_id VARCHAR(255)",
                ]:
                    try: conn.execute(text(sql)); conn.commit()
                    except Exception: pass
        except Exception: pass
        # seed_db uniquement si l'admin n'existe pas encore (première installation)
        if not AdminUser.query.filter_by(username="admin").first():
            try: seed_db()
            except Exception as e: print(f"⚠️ Seeding : {e}")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)

_db_initialized = False

@app.before_request
def ensure_db():
    global _db_initialized
    if not _db_initialized:
        _db_initialized = True
        try: init_db()
        except Exception as e: print(f"[ensure_db] ERREUR : {e}", flush=True)