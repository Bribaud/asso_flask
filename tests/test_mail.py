import smtplib
from unittest.mock import patch

from flask_mail import Message

import app as app_module


def _msg():
    return Message(subject="Sujet", recipients=["x@example.com"], body="Bonjour")


def test_pas_de_mot_de_passe_smtp_en_dur():
    source = open("app.py", encoding="utf-8").read()
    assert "Akf2026" not in source


def test_send_mail_safe_succes(app):
    with app_module.mail.record_messages() as outbox:
        assert app_module.send_mail_safe(_msg()) is True
    assert len(outbox) == 1


def test_send_mail_safe_journalise_l_echec(app, capsys):
    erreur = smtplib.SMTPAuthenticationError(535, b"Authentication failed")
    with patch.object(app_module.mail, "send", side_effect=erreur):
        assert app_module.send_mail_safe(_msg()) is False
    sortie = capsys.readouterr().out
    assert "[mail] échec" in sortie and "SMTPAuthenticationError" in sortie


def test_send_mail_safe_sans_mot_de_passe(app, capsys, monkeypatch):
    monkeypatch.setitem(app.config, "MAIL_PASSWORD", None)
    with patch.object(app_module.mail, "send") as send:
        assert app_module.send_mail_safe(_msg()) is False
    send.assert_not_called()
    assert "MAIL_PASSWORD non défini" in capsys.readouterr().out


def test_email_de_test_reserve_aux_admins(client):
    resp = client.post("/admin/parametres/test-email")
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]


def test_email_de_test_envoye(admin_client):
    with app_module.mail.record_messages() as outbox:
        resp = admin_client.post("/admin/parametres/test-email", follow_redirects=True)
    assert resp.status_code == 200
    assert "E-mail de test envoyé" in resp.get_data(as_text=True)
    assert len(outbox) == 1
    assert outbox[0].recipients == [app_module.MAIL_NOTIFICATIONS]


def test_email_de_test_echec_signale(admin_client):
    with patch.object(app_module.mail, "send", side_effect=Exception("boom")):
        resp = admin_client.post("/admin/parametres/test-email", follow_redirects=True)
    assert "Échec de l&#39;envoi" in resp.get_data(as_text=True)
