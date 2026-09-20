import os
import tempfile
import pytest
from app import app, init_db


@pytest.fixture()
def client():
    database = tempfile.NamedTemporaryFile(delete=False)
    database.close()
    app.config.update(TESTING=True, DATABASE=database.name, SECRET_KEY="test-secret", JWT_SECRET_KEY="jwt-test-secret")
    with app.app_context():
        init_db()
    with app.test_client() as test_client:
        yield test_client
    os.unlink(database.name)


def login(client, email, password, follow_redirects=True):
    return client.post("/auth", data={"action": "login", "email": email, "password": password}, follow_redirects=follow_redirects)


def login_admin(client):
    return login(client, "admin@rijoya.local", "admin123")


def test_home_shows_seed_products(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Arc Desk Lamp" in response.data


def test_register_customer_login_cart_and_checkout(client):
    response = client.post("/auth", data={"action": "register", "name": "Ari", "email": "ari@example.com", "password": "secret"}, follow_redirects=True)
    assert b"Welcome to Rijoya" in response.data
    assert b"Arc Desk Lamp" in client.post("/cart/add/1", follow_redirects=True).data
    assert b"Arc Desk Lamp" in client.get("/cart").data
    response = client.post("/checkout", data={"name": "Ari", "address": "1 Main Street"}, follow_redirects=True)
    assert b"Order confirmed" in response.data


def test_jwt_login_and_identity_api(client):
    response = client.post("/api/auth/login", json={"email": "admin@rijoya.local", "password": "admin123"})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["token_type"] == "Bearer"
    assert payload["role"] == "super_admin"
    identity = client.get("/api/auth/me", headers={"Authorization": f"Bearer {payload['access_token']}"})
    assert identity.status_code == 200
    assert identity.get_json()["role"] == "super_admin"
    assert "*" in identity.get_json()["permissions"]


def test_customer_cannot_access_admin_or_vendor_portals(client):
    login(client, "demo@rijoya.local", "demo-password")
    assert client.get("/admin").status_code == 302
    assert client.get("/vendor/dashboard").status_code == 302
    assert client.post("/admin/product/1/status", data={"status": "rejected"}).status_code == 302


def test_vendor_has_own_portal_and_product_is_pending(client):
    response = client.post("/vendor/register", data={"name": "Test Shop", "email": "shop@example.com", "password": "vendor-secret"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"VENDOR PORTAL" in response.data
    response = client.post("/vendor/dashboard", data={"name": "Test Bowl", "price": "18.50"}, follow_redirects=True)
    assert b"Test Bowl" in response.data
    assert b"pending" in response.data
    assert client.get("/").data.find(b"Test Bowl") == -1


def test_admin_with_role_permissions_can_manage_products_but_not_admin_accounts(client):
    response = login(client, "ops@rijoya.local", "admin123")
    assert response.status_code == 200
    assert b"Manage Rijoya" in response.data
    assert client.post("/admin/product/1/status", data={"status": "rejected"}).status_code == 302
    assert client.post("/admin/admin/create", data={"name": "Nope", "email": "nope@example.com", "password": "secret"}).status_code == 302
    with client.session_transaction() as saved_session:
        assert saved_session["role"] == "admin"


def test_super_admin_can_manage_admin_accounts_and_permissions(client):
    response = login_admin(client)
    assert b"Manage Rijoya" in response.data
    response = client.post("/admin/admin/create", data={"name": "Reports Admin", "email": "reports@example.com", "password": "secret"}, follow_redirects=True)
    assert b"Admin account created" in response.data
    response = client.post("/admin/admin/4/permissions", data={"permissions": ["view_dashboard", "manage_orders"]}, follow_redirects=True)
    assert b"Admin permissions updated" in response.data
    response = client.post("/admin/admin/4/status", data={"status": "suspended"}, follow_redirects=True)
    assert b"suspended" in response.data
    assert b"suspended" in login(client, "reports@example.com", "secret").data


def test_super_admin_can_approve_vendor_product_and_update_order(client):
    client.post("/vendor/register", data={"name": "Pending Shop", "email": "pending@example.com", "password": "secret"})
    client.post("/vendor/dashboard", data={"name": "Pending Bowl", "price": "20.00"})
    login_admin(client)
    assert b"Manage Rijoya" in client.get("/admin").data
    assert client.post("/admin/vendor/3/status", data={"status": "approved"}).status_code == 302
    assert client.post("/admin/product/5/status", data={"status": "approved"}).status_code == 302
    assert b"Pending Bowl" in client.get("/").data
