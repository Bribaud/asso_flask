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


def test_normaliser_database_url():
    f = app_module.normaliser_database_url
    attendu = "postgresql+psycopg2://u:p@h:6543/postgres"
    assert f("postgresql://u:p@h:6543/postgres") == attendu
    assert f("postgres://u:p@h:6543/postgres") == attendu
    assert f("postgresql+psycopg://u:p@h:6543/postgres") == attendu
    assert f("postgresql+psycopg2://u:p@h:6543/postgres") == attendu
    assert f("sqlite:////tmp/akf.db") == "sqlite:////tmp/akf.db"


def test_url_supabase_utilise_psycopg2():
    # Régression : SQLAlchemy 2.1 choisissait psycopg (v3), absent en production
    from sqlalchemy.engine import make_url
    url = make_url(app_module.normaliser_database_url(
        "postgresql://postgres.abc:pw@aws-0-eu-west-3.pooler.supabase.com:6543/postgres"))
    assert url.get_dialect().driver == "psycopg2"
