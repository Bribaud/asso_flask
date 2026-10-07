from unittest.mock import MagicMock, patch

import app as app_module
from app import AdminUser, db


def _supprimer_admins():
    AdminUser.query.delete()
    db.session.commit()


def test_seed_cree_admin_depuis_variable_env(app, monkeypatch):
    _supprimer_admins()
    monkeypatch.setenv("ADMIN_PASSWORD", "un-mot-de-passe-solide")
    app_module.seed_db()
    admin = AdminUser.query.filter_by(username="admin").one()
    assert admin.check_password("un-mot-de-passe-solide")
    assert not admin.check_password("akf2026")


def test_seed_sans_variable_ne_cree_pas_d_admin(app, monkeypatch):
    _supprimer_admins()
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    app_module.seed_db()
    assert AdminUser.query.count() == 0


def test_pas_de_mot_de_passe_admin_en_dur():
    source = open("app.py", encoding="utf-8").read()
    assert "akf2026" not in source


def test_rls_ignoree_hors_postgresql(app):
    # SQLite en test : ne doit rien exécuter ni échouer
    app_module.activer_rls()


def test_rls_activee_sur_toutes_les_tables_postgresql(app):
    conn = MagicMock()
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    engine.connect.return_value.__enter__.return_value = conn
    with patch.object(type(db), "engine", new=engine):
        app_module.activer_rls()
    executes = [str(c.args[0]) for c in conn.execute.call_args_list]
    assert len(executes) == len(db.metadata.tables)
    assert all("ENABLE ROW LEVEL SECURITY" in s for s in executes)
    assert any('"adhesion"' in s for s in executes)
