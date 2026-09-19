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


def test_vendor_can_add_product(client):
    client.post("/vendor/register", data={"name": "Test Shop", "email": "shop@example.com"})
    response = client.post("/products", data={"name": "Test Bowl", "price": "18.50"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Test Bowl" in response.data


def test_checkout_creates_order(client):
    client.post("/auth", data={"action": "register", "name": "Buyer", "email": "buyer@example.com", "password": "secret"})
    client.post("/cart/add/1")
    response = client.post("/checkout", data={"name": "Buyer", "address": "1 Main Street"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Order confirmed" in response.data
