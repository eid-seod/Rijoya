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


def test_customer_registration_session_and_dashboard(client):
    response = client.post("/auth", data={"action": "register", "name": "Ari", "email": "ari@example.com", "password": "secret"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Your Rijoya" in response.data
    with client.session_transaction() as saved:
        assert saved["role"] == "customer"
        assert saved["user_id"]
        assert saved["session_id"]
    with app.app_context():
        row = sqlite3.connect(app.config["DATABASE"]).execute("SELECT user_id, login_time, last_activity FROM sessions").fetchone()
        assert row[0] > 0 and row[1] and row[2]


def test_logout_deletes_server_session(client):
    login(client, "demo@rijoya.local", "demo-password")
    with client.session_transaction() as saved:
        session_id = saved["session_id"]
    client.get("/logout")
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        assert db.execute("SELECT COUNT(*) FROM sessions WHERE id = ?", (session_id,)).fetchone()[0] == 0


def test_inactivity_timeout_clears_session(client):
    login(client, "demo@rijoya.local", "demo-password")
    with client.session_transaction() as saved:
        session_id = saved["session_id"]
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        old = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat()
        db.execute("UPDATE sessions SET last_activity = ? WHERE id = ?", (old, session_id))
        db.commit()
    response = client.get("/customer/dashboard")
    assert response.status_code == 302
    with client.session_transaction() as saved:
        assert "user_id" not in saved


def test_customer_can_browse_cart_checkout_and_history(client):
    login(client, "demo@rijoya.local", "demo-password")
    assert b"Arc Desk Lamp" in client.get("/").data
    client.post("/cart/add/1")
    response = client.post("/checkout", data={"address": "1 Main Street"}, follow_redirects=True)
    assert b"Your orders" in response.data
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        assert db.execute("SELECT COUNT(*) FROM order_items").fetchone()[0] == 1


def test_customer_cannot_access_staff_or_vendor_routes(client):
    login(client, "demo@rijoya.local", "demo-password")
    assert client.get("/admin").status_code == 302
    assert client.get("/vendor/dashboard").status_code == 302
    assert client.post("/admin/product/1/status", data={"status": "rejected"}).status_code == 302


def test_vendor_sees_only_owned_order_fields_and_no_customer_data(client):
    client.post("/vendor/register", data={"name": "Private Shop", "email": "private@example.com", "password": "vendor-secret"})
    vendor_product_response = client.post("/vendor/dashboard", data={"name": "Private Bowl", "price": "18.50"}, follow_redirects=True)
    assert b"Private Bowl" in vendor_product_response.data
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        db.execute("UPDATE vendors SET status = 'approved' WHERE store_name = 'Private Shop'")
        product_id = db.execute("SELECT id FROM products WHERE name = 'Private Bowl'").fetchone()[0]
        customer_id = db.execute("SELECT id FROM users WHERE email = 'demo@rijoya.local'").fetchone()[0]
        order_id = db.execute("INSERT INTO orders (customer_id, total_amount, status, created_at) VALUES (?, 18.5, 'confirmed', ?)", (customer_id, datetime.now(timezone.utc).isoformat())).lastrowid
        db.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, 2, 18.5)", (order_id, product_id))
        db.commit()
    response = client.get("/vendor/dashboard")
    assert b"Order #" in response.data
    assert b"Private Bowl" in response.data
    assert b"Quantity 2" in response.data
    assert b"demo@rijoya.local" not in response.data
    assert b"Demo Customer" not in response.data
    assert b"customer_phone" not in response.data


def test_vendor_cannot_access_another_vendors_product_by_url(client):
    login(client, "vendor@rijoya.local", "vendor123")
    response = client.post("/vendor/product/3/edit", data={"name": "Hijacked", "price": "1"}, follow_redirects=True)
    assert b"Hijacked" not in response.data
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        assert db.execute("SELECT name FROM products WHERE id = 3").fetchone() is None


def test_admin_and_super_admin_dashboards(client):
    response = login(client, "ops@rijoya.local", "admin123")
    assert response.status_code == 200
    assert b"ADMIN" in response.data
    assert b"SUPER ADMIN ONLY" not in response.data
    response = login(client, "admin@rijoya.local", "admin123")
    assert b"SUPER ADMIN ONLY" in response.data


def test_super_admin_can_manage_admin_permissions_and_admin_cannot_create_super_admin(client):
    login(client, "admin@rijoya.local", "admin123")
    response = client.post("/admin/admin/create", data={"name": "Reports Admin", "email": "reports@example.com", "password": "secret"}, follow_redirects=True)
    assert b"Admin account created" in response.data
    response = client.post("/admin/admin/4/permissions", data={"permissions": ["manage_orders", "manage_support"]}, follow_redirects=True)
    assert b"Admin permissions updated" in response.data
    login(client, "ops@rijoya.local", "admin123")
    assert client.post("/admin/admin/create", data={"name": "Nope", "email": "nope@example.com", "password": "secret"}).status_code == 302
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        assert db.execute("SELECT COUNT(*) FROM users WHERE email = 'nope@example.com'").fetchone()[0] == 0


def test_api_uses_session_authentication(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    response = client.post("/api/auth/login", json={"email": "admin@rijoya.local", "password": "admin123"})
    assert response.status_code == 200
    assert response.get_json()["role"] == "super_admin"
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.get_json()["last_login"]
