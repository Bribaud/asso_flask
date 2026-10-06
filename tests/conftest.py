import os
import sys

import pytest

# Variables d'environnement à définir AVANT l'import de app.py
os.environ["DATABASE_URL"] = "sqlite://"          # base SQLite en mémoire
os.environ["SECRET_KEY"] = "test-secret"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"
os.environ["MAIL_PASSWORD"] = "dummy"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)  # generate_carte_membre utilise des chemins relatifs "static/..."

import app as app_module  # noqa: E402


@pytest.fixture()
def app():
    flask_app = app_module.app
    flask_app.config.update(TESTING=True)
    # Aucun e-mail réellement envoyé pendant les tests
    flask_app.extensions["mail"].suppress = True
    # On court-circuite init_db() (seed + import Excel) déclenché au 1er request
    app_module._db_initialized = True

    with flask_app.app_context():
        app_module.db.create_all()
        admin = app_module.AdminUser(username="admin")
        admin.set_password("test-password")
        app_module.db.session.add(admin)
        app_module.db.session.commit()
        yield flask_app
        app_module.db.session.remove()
        app_module.db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def admin_client(client):
    client.post("/admin/login", data={"username": "admin", "password": "test-password"})
    return client
