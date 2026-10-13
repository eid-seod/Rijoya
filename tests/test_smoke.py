import unittest
from decimal import Decimal
from app import create_app
from config import Config
from extensions import db
from models.models import Admin, Customer, Order, OrderItem, Product, ShippingRate


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    ADMIN_EMAIL = "test-admin@example.com"
    ADMIN_PASSWORD = "test-password-123"


class RijoyaSmokeTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_storefront_and_public_api(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/products").status_code, 200)
        payload = self.client.get("/api/products").get_json()
        self.assertGreaterEqual(len(payload["items"]), 1)
        self.assertEqual(self.client.get("/health").get_json()["status"], "ok")

    def test_admin_login_and_restricted_pages(self):
        self.assertEqual(self.client.get("/admin/").status_code, 302)
        with self.client.session_transaction() as sess:
            sess["_csrf_token"] = "test"
        response = self.client.post("/admin/login", data={
            "email": "test-admin@example.com", "password": "test-password-123", "csrf_token": "test"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("نظرة عامة", response.get_data(as_text=True))

    def test_admin_json_resource_crud(self):
        self.assertEqual(self.client.get("/api/admin/products").status_code, 401)
        response = self.client.post("/admin/login", data={
            "email": "test-admin@example.com", "password": "test-password-123"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        category_response = self.client.post("/api/admin/categories", json={"name": "API category"})
        self.assertEqual(category_response.status_code, 201)
        category_id = category_response.get_json()["item"]["id"]
        product_response = self.client.post("/api/admin/products", json={
            "name": "API product", "sku": "API-001", "price": "49.90",
            "stock": 7, "category_id": category_id
        })
        self.assertEqual(product_response.status_code, 201)
        product_id = product_response.get_json()["item"]["id"]
        update = self.client.patch(f"/api/admin/products/{product_id}", json={"stock": 3})
        self.assertEqual(update.get_json()["item"]["stock"], 3)
        deleted = self.client.delete(f"/api/admin/products/{product_id}")
        self.assertFalse(deleted.get_json()["item"]["is_active"])

    def test_guest_checkout_creates_cod_order_and_snapshots(self):
        with self.app.app_context():
            product = Product.query.filter_by(is_active=True).first()
            initial_stock = product.stock
            product_id = product.id
            initial_name = product.name
            initial_price = product.price
        response = self.client.post(f"/cart/add/{product_id}", data={"quantity": 2}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        response = self.client.post("/checkout", data={
            "full_name": "Test Buyer", "email": "buyer@example.com", "phone": "+201001234567",
            "governorate": "القاهرة", "city": "القاهرة", "area": "المعادي",
            "address": "12 Example Street, Cairo", "notes": "",
            "submit": "Place order",
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("ORD-", response.get_data(as_text=True))
        with self.app.app_context():
            order = Order.query.filter_by(email="buyer@example.com").one()
            self.assertEqual(order.payment_method, "cod")
            self.assertEqual(len(order.items), 1)
            self.assertEqual(order.items[0].quantity, 2)
            self.assertEqual(order.items[0].product_name, initial_name)
            self.assertEqual(order.items[0].unit_price, initial_price)
            self.assertEqual(db.session.get(Product, product_id).stock, initial_stock - 2)
            self.assertEqual(order.order_number, f"ORD-{order.created_at:%Y%m%d}-{order.id:06d}")
            product = db.session.get(Product, product_id)
            product.name = "Edited after order"
            product.price = initial_price + 100
            db.session.commit()
            self.assertEqual(order.items[0].product_name, initial_name)
            self.assertEqual(order.items[0].unit_price, initial_price)

    def test_cancellation_restores_inventory_once(self):
        with self.app.app_context():
            product = Product.query.filter_by(is_active=True).first()
            product.stock -= 1
            order = Order(order_number="ORD-TEST-CANCEL", customer_name="Test", phone="+201000000000",
                governorate="القاهرة", address="Test address", subtotal=product.price,
                shipping_fee=Decimal("0"), total=product.price, payment_method="cod", status="new")
            db.session.add(order)
            db.session.flush()
            db.session.add(OrderItem(order=order, product_id=product.id, product_name=product.name,
                sku=product.sku, unit_price=product.price, quantity=1, line_total=product.price))
            db.session.commit()
            order_id, product_id, reserved_stock = order.id, product.id, product.stock
        self.client.post("/admin/login", data={
            "email": "test-admin@example.com", "password": "test-password-123"
        }, follow_redirects=True)
        response = self.client.post(f"/admin/orders/{order_id}", data={"status": "cancelled"})
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(db.session.get(Product, product_id).stock, reserved_stock + 1)
        self.client.post(f"/admin/orders/{order_id}", data={"status": "new"})
        with self.app.app_context():
            self.assertEqual(db.session.get(Product, product_id).stock, reserved_stock + 1)
            self.assertEqual(db.session.get(Order, order_id).status, "cancelled")

    def test_only_one_admin_seeded(self):
        with self.app.app_context():
            self.assertEqual(Admin.query.count(), 1)
            self.assertEqual(Customer.query.count(), 1)
            self.assertEqual(Order.query.count(), 1)
            self.assertEqual(Order.query.first().email, "sample.customer@rijoya.local")
            self.assertEqual(ShippingRate.query.count(), 27)


if __name__ == "__main__":
    unittest.main()
