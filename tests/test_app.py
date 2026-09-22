import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from app import app, init_db


@pytest.fixture()
def client():
    database = tempfile.NamedTemporaryFile(delete=False)
    database.close()
    app.config.update(TESTING=True, DATABASE=database.name, SECRET_KEY="test-secret", PERMANENT_SESSION_LIFETIME=timedelta(minutes=30))
    with app.app_context():
        init_db()
    with app.test_client() as test_client:
        yield test_client
    os.unlink(database.name)


def login(client, email, password, follow_redirects=True):
    return client.post("/auth", data={"action": "login", "email": email, "password": password}, follow_redirects=follow_redirects)


def test_public_blueprint_catalog_only_shows_approved_products(client):
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        db.execute("INSERT INTO products (name, price, vendor_id, status) VALUES ('Hidden Pending Product', 10, 1, 'pending')")
        db.commit()
    response = client.get("/products")
    assert response.status_code == 200
    assert b"Arc Desk Lamp" in response.data
    assert b"Hidden Pending Product" not in response.data
    assert b"Add something good" not in response.data


def test_customer_registration_session_and_shop_dashboard(client):
    response = client.post("/auth", data={"action": "register", "name": "Ari", "email": "ari@example.com", "password": "secret"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Your Rijoya" in response.data
    with client.session_transaction() as saved:
        assert saved["role"] == "customer"
        assert saved["user_id"] and saved["session_id"]


def test_vendor_application_is_persistent_and_approved_vendor_authenticates(client):
    login(client, "demo@rijoya.local", "demo-password")
    response = client.post("/vendor/apply", data={"store_name": "Ari Studio"}, follow_redirects=True)
    assert b"Application status" in response.data
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        row = db.execute("SELECT vendors.user_id, vendors.status FROM vendors JOIN users ON users.id = vendors.user_id WHERE users.email = 'demo@rijoya.local'").fetchone()
        assert row == (1, "pending")
        db.execute("UPDATE vendors SET status = 'approved' WHERE user_id = 1")
        db.commit()
    client.get("/logout")
    login(client, "demo@rijoya.local", "demo-password")
    response = client.get("/vendor/dashboard")
    assert response.status_code == 200
    assert b"VENDOR DASHBOARD" in response.data


def test_vendor_required_redirects_unapproved_user_to_application(client):
    login(client, "demo@rijoya.local", "demo-password")
    response = client.get("/vendor/dashboard")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/vendor/apply")


def test_vendor_product_creation_is_separate_post_route(client):
    login(client, "vendor@rijoya.local", "vendor123")
    assert client.post("/products", data={"name": "Should Not Create", "price": "5"}).status_code == 405
    response = client.post("/vendor/products/new", data={"name": "Vendor Bowl", "price": "18.50"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Vendor Bowl" in response.data
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        row = db.execute("SELECT products.status, vendors.user_id FROM products JOIN vendors ON vendors.id = products.vendor_id WHERE products.name = 'Vendor Bowl'").fetchone()
        assert row == ("pending", 4)


def test_vendor_sees_only_own_products_and_safe_order_fields(client):
    login(client, "vendor@rijoya.local", "vendor123")
    response = client.get("/vendor/dashboard")
    assert response.status_code == 200
    assert b"Arc Desk Lamp" in response.data
    assert b"Customer names" not in response.data
    assert b"customer_phone" not in response.data


def test_vendor_cannot_access_other_vendor_product_by_url(client):
    login(client, "vendor@rijoya.local", "vendor123")
    response = client.post("/vendor/product/999/edit", data={"name": "Hijacked", "price": "1"}, follow_redirects=True)
    assert b"Hijacked" not in response.data


def test_customer_cannot_access_vendor_or_admin_routes(client):
    login(client, "demo@rijoya.local", "demo-password")
    assert client.get("/admin").status_code == 302
    assert client.get("/vendor/dashboard").status_code == 302
    assert client.post("/vendor/products/new", data={"name": "Nope", "price": "1"}).status_code == 302


def test_admin_and_super_admin_blueprint_dashboard(client):
    response = login(client, "ops@rijoya.local", "admin123")
    assert response.status_code == 200
    assert b"ADMIN" in response.data
    assert b"SUPER ADMIN ONLY" not in response.data
    response = login(client, "admin@rijoya.local", "admin123")
    assert b"SUPER ADMIN ONLY" in response.data


def test_super_admin_preserves_vendor_approval_flow(client):
    login(client, "admin@rijoya.local", "admin123")
    response = client.post("/admin/vendor/1/status", data={"status": "rejected"}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        assert db.execute("SELECT status FROM vendors WHERE id = 1").fetchone()[0] == "rejected"


def test_session_logout_and_api_identity(client):
    login(client, "admin@rijoya.local", "admin123")
    with client.session_transaction() as saved:
        session_id = saved["session_id"]
    assert client.get("/api/auth/me").status_code == 200
    client.get("/logout")
    assert client.get("/api/auth/me").status_code == 401
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        assert db.execute("SELECT COUNT(*) FROM sessions WHERE id = ?", (session_id,)).fetchone()[0] == 0
