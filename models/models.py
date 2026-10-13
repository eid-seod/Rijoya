from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Customer(UserMixin, db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=False, default="")
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    cart_items = db.relationship("CartItem", back_populates="customer", cascade="all, delete-orphan")
    orders = db.relationship("Order", back_populates="customer")

    @property
    def is_admin(self):
        return False

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return f"customer:{self.id}"


class Admin(UserMixin, db.Model):
    __tablename__ = "admins"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    @property
    def is_admin(self):
        return True

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return f"admin:{self.id}"


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.String(500), default="")
    image = db.Column(db.String(255), default="")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    products = db.relationship("Product", back_populates="category")


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Numeric(10, 2), nullable=False)
    compare_at_price = db.Column(db.Numeric(10, 2), nullable=True)
    stock = db.Column(db.Integer, default=0, nullable=False)
    sku = db.Column(db.String(60), unique=True, nullable=False)
    image = db.Column(db.String(255), default="")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    category = db.relationship("Category", back_populates="products")

    @property
    def available(self):
        return self.is_active and self.stock > 0

    @property
    def on_sale(self):
        return self.compare_at_price is not None and self.compare_at_price > self.price


class CartItem(db.Model):
    __tablename__ = "cart_items"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    customer = db.relationship("Customer", back_populates="cart_items")
    product = db.relationship("Product")
    __table_args__ = (db.UniqueConstraint("customer_id", "product_id", name="uq_cart_customer_product"),)


class ShippingRate(db.Model):
    __tablename__ = "shipping_rates"
    id = db.Column(db.Integer, primary_key=True)
    governorate = db.Column(db.String(100), nullable=False, index=True)
    city = db.Column(db.String(100), nullable=False, default="")
    area = db.Column(db.String(100), nullable=False, default="")
    fee = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    __table_args__ = (db.UniqueConstraint("governorate", "city", "area", name="uq_shipping_location"),)


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    customer_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), default="")
    phone = db.Column(db.String(30), nullable=False)
    governorate = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), default="")
    area = db.Column(db.String(100), default="")
    address = db.Column(db.String(500), nullable=False)
    notes = db.Column(db.String(1000), default="")
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    shipping_fee = db.Column(db.Numeric(10, 2), nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(20), nullable=False, default="cod")
    status = db.Column(db.String(24), nullable=False, default="new", index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    customer = db.relationship("Customer", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (db.CheckConstraint("payment_method = 'cod'", name="ck_orders_cod_only"),)


class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name = db.Column(db.String(160), nullable=False)
    sku = db.Column(db.String(60), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    line_total = db.Column(db.Numeric(10, 2), nullable=False)
    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product")
