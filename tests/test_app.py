import os
import tempfile
import pytest
from app import app, init_db


@pytest.fixture()
def client():
    database = tempfile.NamedTemporaryFile(delete=False)
    database.close()
    app.config.update(TESTING=True, DATABASE=database.name, SECRET_KEY="test-secret")
    with app.app_context():
        init_db()
    with app.test_client() as test_client:
        yield test_client
    os.unlink(database.name)


def login_admin(client):
    return client.post("/auth", data={"action": "login", "email": "admin@rijoya.local", "password": "admin123"}, follow_redirects=True)


def test_home_shows_seed_products(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Arc Desk Lamp" in response.data


def test_register_login_and_add_to_cart(client):
    response = client.post("/auth", data={"action": "register", "name": "Ari", "email": "ari@example.com", "password": "secret"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Welcome to Rijoya" in response.data
    response = client.post("/cart/add/1", follow_redirects=True)
    assert b"Product added" in response.data
    response = client.get("/cart")
    assert b"Arc Desk Lamp" in response.data


def test_vendor_can_add_product_for_admin_review(client):
    client.post("/vendor/register", data={"name": "Test Shop", "email": "shop@example.com"})
    response = client.post("/products", data={"name": "Test Bowl", "price": "18.50"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Test Bowl" in response.data
    assert b"submitted for admin approval" in response.data


def test_checkout_creates_order(client):
    client.post("/auth", data={"action": "register", "name": "Buyer", "email": "buyer@example.com", "password": "secret"})
    client.post("/cart/add/1")
    response = client.post("/checkout", data={"name": "Buyer", "address": "1 Main Street"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Order confirmed" in response.data


def test_super_admin_can_approve_vendor_and_product(client):
    client.post("/vendor/register", data={"name": "Pending Shop", "email": "pending@example.com"})
    client.post("/products", data={"name": "Pending Bowl", "price": "20.00"})
    response = login_admin(client)
    assert response.status_code == 200
    assert b"Manage Rijoya" in response.data
    with client.session_transaction() as saved_session:
        assert saved_session["is_admin"] is True
    client.post("/admin/vendor/3/status", data={"status": "approved"})
    client.post("/admin/product/5/status", data={"status": "approved"})
    assert b"Pending Bowl" in client.get("/").data


def test_super_admin_can_edit_delete_and_update_order(client):
    client.post("/auth", data={"action": "register", "name": "Order Buyer", "email": "order@example.com", "password": "secret"})
    client.post("/cart/add/1")
    client.post("/checkout", data={"name": "Order Buyer", "address": "1 Main Street"})
    login_admin(client)
    response = client.post("/admin/product/1/edit", data={"name": "Updated Lamp", "price": "99.00"}, follow_redirects=True)
    assert b"Product updated" in response.data
    assert b"Updated Lamp" in client.get("/admin").data
    client.post("/admin/order/1/status", data={"status": "shipped"})
    assert b"shipped" in client.get("/admin").data
    response = client.post("/admin/product/4/delete", follow_redirects=True)
    assert b"Product deleted" in response.data
    assert b"Alba Ceramic Mug" not in client.get("/admin").data
