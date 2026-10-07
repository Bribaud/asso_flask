import hashlib
import hmac
import json
import time
from unittest.mock import patch

import app as app_module
from app import Adhesion, Don, db

WEBHOOK_SECRET = "whsec_test_secret"


def _signed(payload: dict, secret=WEBHOOK_SECRET):
    body = json.dumps(payload).encode()
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {"Stripe-Signature": f"t={ts},v1={sig}", "Content-Type": "application/json"}


def _event(obj, type_="checkout.session.completed"):
    return {"id": "evt_1", "object": "event", "type": type_, "data": {"object": obj}}


def _adhesion(statut="en_attente"):
    adh = Adhesion(prenom="Moussa", nom="Diop", email="moussa@example.com", statut=statut)
    db.session.add(adh)
    db.session.commit()
    return adh


# ── Webhook ──────────────────────────────────────────────────────────────────

def test_webhook_non_configure(client, monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    assert client.post("/stripe/webhook", data=b"{}").status_code == 503


def test_webhook_signature_invalide(client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    body, headers = _signed(_event({"id": "cs_1"}), secret="mauvais_secret")
    assert client.post("/stripe/webhook", data=body, headers=headers).status_code == 400


def test_webhook_sans_signature(client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    assert client.post("/stripe/webhook", data=b"{}").status_code == 400


def test_webhook_active_adhesion_une_seule_fois(client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    adh = _adhesion()
    body, headers = _signed(_event({
        "id": "cs_1", "payment_status": "paid", "metadata": {"adhesion_id": str(adh.id)},
    }))
    with patch.object(app_module, "send_mail_safe") as send:
        assert client.post("/stripe/webhook", data=body, headers=headers).status_code == 200
        # Stripe peut renvoyer l'événement : aucun second e-mail
        assert client.post("/stripe/webhook", data=body, headers=headers).status_code == 200
    db.session.refresh(adh)
    assert adh.statut == "actif"
    assert adh.matricule == f"AKF-{adh.id:04d}"
    assert send.call_count == 2  # carte au membre + notification, une seule fois


def test_webhook_ignore_paiement_non_confirme(client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    adh = _adhesion()
    body, headers = _signed(_event({
        "id": "cs_1", "payment_status": "unpaid", "metadata": {"adhesion_id": str(adh.id)},
    }))
    assert client.post("/stripe/webhook", data=body, headers=headers).status_code == 200
    db.session.refresh(adh)
    assert adh.statut == "en_attente"


def test_webhook_marque_don_paye(client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    db.session.add(Don(nom="Awa", email="awa@example.com", montant=25.0, stripe_session_id="cs_don"))
    db.session.commit()
    body, headers = _signed(_event({
        "id": "cs_don", "payment_status": "paid", "metadata": {"type": "don"},
    }))
    with patch.object(app_module, "send_mail_safe"):
        assert client.post("/stripe/webhook", data=body, headers=headers).status_code == 200
    assert Don.query.one().statut == "paye"


# ── Page de succès ───────────────────────────────────────────────────────────

def test_success_sans_session_redirige(client):
    assert client.get("/adhesion/success").status_code == 302


def test_success_stripe_en_erreur_ne_fuit_pas_de_trace(client):
    with patch.object(app_module.stripe.checkout.Session, "retrieve", side_effect=Exception("boom")):
        resp = client.get("/adhesion/success?session_id=cs_x")
    assert resp.status_code == 302
    assert "boom" not in resp.get_data(as_text=True)


def test_success_active_adhesion_payee(client):
    adh = _adhesion()
    fake = type("S", (), {"payment_status": "paid", "metadata": {"adhesion_id": str(adh.id)}})()
    with patch.object(app_module.stripe.checkout.Session, "retrieve", return_value=fake), \
            patch.object(app_module, "send_mail_safe"):
        resp = client.get("/adhesion/success?session_id=cs_1")
    assert resp.status_code == 200
    db.session.refresh(adh)
    assert adh.statut == "actif"


# ── Dons ─────────────────────────────────────────────────────────────────────

def _post_don(client, **data):
    fake = type("S", (), {"id": "cs_don", "url": "https://stripe.test/pay"})()
    with patch.object(app_module.stripe.checkout.Session, "create", return_value=fake) as create:
        resp = client.post("/don", data=data)
    return resp, create


def test_don_euro(client):
    resp, create = _post_don(client, montant="25", devise="EUR", nom="Awa", email="a@x.fr")
    assert resp.status_code == 303
    assert create.call_args.kwargs["line_items"][0]["price_data"]["unit_amount"] == 2500
    don = Don.query.one()
    assert don.montant == 25.0 and don.statut == "en_attente"


def test_don_fcfa_converti_en_euros(client):
    # 6 560 FCFA ≈ 10 € ; avant le correctif, ce don était facturé 6 560 €
    resp, create = _post_don(client, montant="6560", devise="FCFA")
    assert resp.status_code == 303
    assert create.call_args.kwargs["line_items"][0]["price_data"]["unit_amount"] == 1000
    assert Don.query.one().montant == 10.0


def test_don_montant_hors_limites(client):
    for montant in ("0", "0.5", "10001", "-5"):
        resp, create = _post_don(client, montant=montant, devise="EUR")
        assert resp.status_code == 302
        create.assert_not_called()
    assert Don.query.count() == 0


def test_don_montant_invalide(client):
    resp, create = _post_don(client, montant="abc", devise="EUR")
    assert resp.status_code == 302
    create.assert_not_called()


def test_don_devise_inconnue(client):
    resp, create = _post_don(client, montant="10", devise="USD")
    assert resp.status_code == 302
    create.assert_not_called()


def test_don_erreur_stripe(client):
    with patch.object(app_module.stripe.checkout.Session, "create", side_effect=Exception("down")):
        resp = client.post("/don", data={"montant": "10", "devise": "EUR"})
    assert resp.status_code == 302
    assert Don.query.count() == 0


# ── Sécurité ─────────────────────────────────────────────────────────────────

def test_route_debug_supprimee(client):
    assert client.get("/debug/stripe/cs_test_123").status_code == 404


def test_pas_de_cle_stripe_en_dur():
    source = open("app.py", encoding="utf-8").read()
    assert "sk_test_" not in source and "sk_live_" not in source


def test_checkout_sans_payment_method_types(client):
    # L'API Stripe récente refuse ce paramètre (les moyens de paiement se règlent dans le dashboard)
    _, create = _post_don(client, montant="10", devise="EUR")
    assert "payment_method_types" not in create.call_args.kwargs

    client.post("/adhesion", data={"prenom": "A", "nom": "B", "email": "a@b.fr"})
    fake = type("S", (), {"id": "cs_x", "url": "https://stripe.test/pay"})()
    with patch.object(app_module.stripe.checkout.Session, "create", return_value=fake) as create:
        client.post("/adhesion/payer")
    assert "payment_method_types" not in create.call_args.kwargs
