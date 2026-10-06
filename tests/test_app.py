from unittest.mock import patch

import pytest

import app as app_module
from app import Adhesion, ContactMessage, Projet, db


# ── Pages publiques ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "/", "/presentation", "/projets", "/actualites", "/evenements",
    "/contact", "/adhesion", "/don", "/mentions-legales",
    "/api/projets", "/api/actualites",
])
def test_pages_publiques(client, url):
    assert client.get(url).status_code == 200


def test_detail_projet(client):
    db.session.add(Projet(titre="Puits", slug="puits", description="Un puits"))
    db.session.commit()
    resp = client.get("/projets/puits")
    assert resp.status_code == 200
    assert "Puits" in resp.get_data(as_text=True)


def test_page_inexistante(client):
    assert client.get("/projets/nexiste-pas").status_code == 404


# ── Formulaires ──────────────────────────────────────────────────────────────

def test_contact_enregistre_message(client):
    resp = client.post("/contact", data={
        "nom": "Awa", "email": "awa@example.com", "sujet": "Test", "message": "Bonjour",
    })
    assert resp.status_code == 302
    assert ContactMessage.query.count() == 1


def test_contact_champs_manquants(client):
    client.post("/contact", data={"nom": "", "email": "", "message": ""})
    assert ContactMessage.query.count() == 0


def test_adhesion_puis_confirmation(client):
    resp = client.post("/adhesion", data={
        "prenom": "Moussa", "nom": "Diop", "email": "moussa@example.com",
        "etudiant": "oui", "type_adhesion": "membre_actif",
    })
    assert resp.status_code == 302
    assert "/adhesion/confirme" in resp.headers["Location"]
    adh = Adhesion.query.one()
    assert adh.statut == "en_attente"

    resp = client.get("/adhesion/confirme")
    assert resp.status_code == 200


def test_adhesion_payer_cree_session_stripe(client):
    client.post("/adhesion", data={
        "prenom": "Moussa", "nom": "Diop", "email": "moussa@example.com", "etudiant": "oui",
    })
    fake = type("S", (), {"id": "cs_test_123", "url": "https://stripe.test/pay"})()
    with patch.object(app_module.stripe.checkout.Session, "create", return_value=fake) as create:
        resp = client.post("/adhesion/payer")
    assert resp.status_code == 303
    assert resp.headers["Location"] == "https://stripe.test/pay"
    montant = create.call_args.kwargs["line_items"][0]["price_data"]["unit_amount"]
    assert montant == app_module.ADHESION_PRIX["etudiant"]
    assert Adhesion.query.one().stripe_session_id == "cs_test_123"


# ── Admin ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", ["/admin", "/admin/adhesions", "/admin/cotisations"])
def test_admin_protege(client, url):
    resp = client.get(url)
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]


def test_admin_mauvais_mot_de_passe(client):
    client.post("/admin/login", data={"username": "admin", "password": "faux"})
    assert client.get("/admin").status_code == 302


@pytest.mark.parametrize("url", [
    "/admin", "/admin/projets", "/admin/actualites", "/admin/bureau",
    "/admin/adhesions", "/admin/dons", "/admin/messages", "/admin/evenements",
    "/admin/cotisations", "/admin/envoyer-email", "/admin/parametres",
])
def test_pages_admin(admin_client, url):
    assert admin_client.get(url).status_code == 200


def test_cotisations_generees_pour_membres_actifs(admin_client):
    db.session.add_all([
        Adhesion(prenom="A", nom="Etudiant", email="a@x.fr", etudiant="oui", statut="actif"),
        Adhesion(prenom="B", nom="Pro", email="b@x.fr", etudiant="non", statut="actif"),
        Adhesion(prenom="C", nom="Attente", email="c@x.fr", statut="en_attente"),
    ])
    db.session.commit()
    admin_client.get("/admin/cotisations?mois=1&annee=2026")
    cots = app_module.Cotisation.query.filter_by(mois=1, annee=2026).all()
    assert sorted(c.montant for c in cots) == [5.0, 10.0]


# ── Helpers ──────────────────────────────────────────────────────────────────

def test_make_slug():
    assert app_module.make_slug("Éducation à Koungheul !") == "education-a-koungheul"


def test_generate_carte_membre_png():
    data = app_module.generate_carte_membre("Awa", "Sy", "AKF-0001")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
