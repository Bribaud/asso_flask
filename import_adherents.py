"""
Script d'import des adhérents depuis le fichier Google Forms Excel
Placer ce fichier à la racine du projet (même niveau que app.py)
Lancer : python import_adherents.py
"""

import pandas as pd
from app import app, db, Adhesion
from datetime import datetime

FICHIER = "Formulaire_sans_titdatare__réponses___1_.xlsx"

def nettoyer_telephone(tel):
    if tel is None: return ""
    t = str(tel).strip()
    # Convertir les notations scientifiques (ex: 6.52374657E8)
    try:
        if 'E' in t.upper():
            t = str(int(float(t)))
    except: pass
    return t[:50]

def nettoyer_nom(nom):
    if not nom: return "", ""
    parts = str(nom).strip().split()
    if len(parts) >= 2:
        # Essayer de détecter si le NOM est en majuscules
        for i, p in enumerate(parts):
            if p.isupper() and len(p) > 1:
                nom_fam = p
                prenom  = " ".join(parts[:i] + parts[i+1:])
                return prenom.strip(), nom_fam.strip()
        # Sinon premier mot = prénom, reste = nom
        return parts[0], " ".join(parts[1:])
    return str(nom).strip(), ""

def nettoyer_age(age):
    if age is None: return None
    a = str(age).strip().replace(" ans","").replace("ans","")
    try: return int(float(a))
    except: return None

with app.app_context():
    df = pd.read_excel(FICHIER)
    print(f"✅ Fichier lu : {len(df)} lignes")
    print(f"Colonnes : {list(df.columns[:5])}...\n")

    importes  = 0
    ignores   = 0
    doublons  = 0

    for _, row in df.iterrows():
        nom_complet = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
        ville       = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
        telephone   = nettoyer_telephone(row.iloc[3]) if pd.notna(row.iloc[3]) else ""
        email       = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else ""
        age         = nettoyer_age(row.iloc[5]) if pd.notna(row.iloc[5]) else None
        sexe        = str(row.iloc[6]).strip() if pd.notna(row.iloc[6]) else ""
        marie       = str(row.iloc[7]).strip() if pd.notna(row.iloc[7]) else ""
        motivation  = str(row.iloc[8]).strip() if pd.notna(row.iloc[8]) else ""
        competences = str(row.iloc[12]).strip() if pd.notna(row.iloc[12]) else ""
        domaines    = str(row.iloc[14]).strip() if pd.notna(row.iloc[14]) else ""
        role        = str(row.iloc[19]).strip() if pd.notna(row.iloc[19]) else ""

        if not email or email == "nan":
            ignores += 1
            continue

        # Vérifier doublon par email
        existant = Adhesion.query.filter_by(email=email).first()
        if existant:
            doublons += 1
            print(f"  ⚠️  Doublon ignoré : {email}")
            continue

        prenom, nom = nettoyer_nom(nom_complet)
        if not prenom:
            prenom = nom_complet
            nom    = ""

        # Civilité basée sur le sexe
        civilite = "Mme" if "femme" in sexe.lower() or "féminin" in sexe.lower() else "M."

        # Motivation complète
        motivation_complete = motivation
        if competences and competences != "nan":
            motivation_complete += f"\n\nCompétences : {competences}"
        if domaines and domaines != "nan":
            motivation_complete += f"\n\nDomaines : {domaines}"

        # Type adhésion basé sur le rôle proposé
        type_map = {
            "responsable projet": "membre_actif",
            "membre actif":       "membre_actif",
            "chargé des finances":"membre_bienfaiteur",
            "secrétaire":         "membre_actif",
        }
        type_adhesion = "membre_actif"
        for k, v in type_map.items():
            if k in role.lower():
                type_adhesion = v
                break

        adhesion = Adhesion(
            civilite      = civilite,
            prenom        = prenom or nom_complet,
            nom           = nom,
            email         = email,
            telephone     = telephone,
            ville         = ville,
            pays          = "France",
            type_adhesion = type_adhesion,
            motivation    = motivation_complete[:2000] if motivation_complete else "",
            statut        = "actif",   # Déjà membres fondateurs
        )

        db.session.add(adhesion)
        importes += 1
        print(f"  ✅ {prenom} {nom} ({email}) — {ville}")

    db.session.commit()
    print(f"\n{'='*50}")
    print(f"✅ Import terminé !")
    print(f"   Importés  : {importes}")
    print(f"   Doublons  : {doublons}")
    print(f"   Ignorés   : {ignores}")
    print(f"{'='*50}")