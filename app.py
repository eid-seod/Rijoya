from pathlib import Path
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "rijoya.db"
SCHEMA = BASE_DIR / "schema.sql"
SESSION_TIMEOUT_MINUTES = 30

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("FLASK_SECRET_KEY", "change-this-secret-key"),
    DATABASE=DATABASE,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=SESSION_TIMEOUT_MINUTES),
)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db():
    if "db" not in g:
        if not Path(app.config["DATABASE"]).exists() or database_needs_initialization():
            init_db()
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def database_needs_initialization():
    if not Path(app.config["DATABASE"]).exists():
        return True
    db = sqlite3.connect(app.config["DATABASE"])
    required = {"users", "sessions", "order_items", "addresses"}
    existing = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
    db.close()
    return not required.issubset(existing)


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(app.config["DATABASE"])
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA.read_text())
    for email, password in {
        "demo@rijoya.local": "demo-password",
        "admin@rijoya.local": "admin123",
        "ops@rijoya.local": "admin123",
        "vendor@rijoya.local": "vendor123",
    }.items():
        db.execute("UPDATE users SET password_hash = ?, status = 'active' WHERE email = ?", (generate_password_hash(password), email))
    db.commit()
    db.close()


def role_id(name):
    row = get_db().execute("SELECT id FROM roles WHERE name = ?", (name,)).fetchone()
    return row["id"]


def find_user(email):
    return get_db().execute(
        "SELECT users.*, roles.name AS role_name FROM users JOIN roles ON roles.id = users.role_id WHERE users.email = ?",
        (email,),
    ).fetchone()


def permissions_for(user):
    db = get_db()
    permissions = {row["name"] for row in db.execute(
        "SELECT permissions.name FROM permissions JOIN role_permissions ON role_permissions.permission_id = permissions.id WHERE role_permissions.role_id = ?",
        (user["role_id"],),
    ).fetchall()}
    permissions.update(row["name"] for row in db.execute(
        "SELECT permissions.name FROM permissions JOIN user_permissions ON user_permissions.permission_id = permissions.id WHERE user_permissions.user_id = ?",
        (user["id"],),
    ).fetchall())
    return {"*"} if user["role_name"] == "super_admin" else permissions


def identity_from_session():
    if hasattr(g, "identity"):
        return g.identity
    user_id = session.get("user_id")
    session_id = session.get("session_id")
    if not user_id or not session_id:
        g.identity = None
        return None
    db = get_db()
    active = db.execute(
        "SELECT sessions.*, users.status FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.id = ? AND sessions.user_id = ?",
        (session_id, user_id),
    ).fetchone()
    if not active or active["status"] != "active":
        session.clear()
        g.identity = None
        return None
    try:
        last_activity = datetime.fromisoformat(active["last_activity"])
    except ValueError:
        last_activity = datetime.now(timezone.utc) - timedelta(minutes=SESSION_TIMEOUT_MINUTES + 1)
    if datetime.now(timezone.utc) - last_activity > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
        db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        db.commit()
        session.clear()
        g.identity = None
        return None
    user = db.execute(
        "SELECT users.*, roles.name AS role_name FROM users JOIN roles ON roles.id = users.role_id WHERE users.id = ? AND users.status = 'active'",
        (user_id,),
    ).fetchone()
    if not user:
        session.clear()
        g.identity = None
        return None
    db.execute("UPDATE sessions SET last_activity = ? WHERE id = ?", (utc_now(), session_id))
    db.commit()
    vendor = db.execute("SELECT * FROM vendors WHERE user_id = ?", (user_id,)).fetchone()
    g.identity = {"user": user, "role": user["role_name"], "permissions": permissions_for(user), "vendor": vendor, "session": active}
    return g.identity


def current_user():
    identity = identity_from_session()
    return identity["user"] if identity else None


def is_api_request():
    return request.path.startswith("/api/") or request.is_json


def unauthorized():
    if is_api_request():
        return jsonify(error="Authentication required"), 401
    flash("Please log in first.", "error")
    return redirect(url_for("auth", next=request.path))


def forbidden(message="You do not have permission to perform this action."):
    if is_api_request():
        return jsonify(error=message), 403
    flash(message, "error")
    return redirect(request.referrer or url_for("home"))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not identity_from_session():
            return unauthorized()
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            identity = identity_from_session()
            if not identity:
                return unauthorized()
            if identity["role"] == "super_admin" or identity["role"] in roles:
                return view(*args, **kwargs)
            return forbidden("Your role cannot access this area.")
        return wrapped
    return decorator


def admin_required(view):
    return role_required("admin", "super_admin")(view)


def super_admin_required(view):
    return role_required("super_admin")(view)


def vendor_required(view):
    return role_required("vendor")(view)


def permission_required(permission):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            identity = identity_from_session()
            if not identity:
                return unauthorized()
            if identity["role"] == "super_admin" or permission in identity["permissions"]:
                return view(*args, **kwargs)
            return forbidden(f"The '{permission}' permission is required.")
        return wrapped
    return decorator


def create_session(user):
    db = get_db()
    session_id = secrets.token_urlsafe(32)
    now = utc_now()
    db.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
    db.execute("INSERT INTO sessions (id, user_id, login_time, last_activity, ip_address) VALUES (?, ?, ?, ?, ?)", (session_id, user["id"], now, now, request.remote_addr or "unknown"))
    db.commit()
    session.clear()
    session.permanent = True
    session.update(user_id=user["id"], role=user["role_name"], session_id=session_id)


def destroy_session():
    session_id = session.get("session_id")
    if session_id:
        get_db().execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        get_db().commit()
    session.clear()


def get_cart_items():
    ids = session.get("cart", [])
    if not ids:
        return []
    marks = ",".join("?" for _ in ids)
    return get_db().execute(
        f"SELECT products.*, vendors.store_name AS vendor_name FROM products JOIN vendors ON vendors.id = products.vendor_id WHERE products.id IN ({marks}) AND products.status = 'approved' AND vendors.status = 'approved'",
        ids,
    ).fetchall()


@app.context_processor
def shared_template_data():
    identity = identity_from_session()
    return {
        "cart_count": len(session.get("cart", [])),
        "current_user": identity["user"]["username"] if identity else None,
        "current_role": identity["role"] if identity else None,
        "is_admin": bool(identity and identity["role"] in {"admin", "super_admin"}),
        "is_super_admin": bool(identity and identity["role"] == "super_admin"),
        "is_vendor": bool(identity and identity["role"] == "vendor"),
        "permissions": sorted(identity["permissions"]) if identity else [],
    }


@app.route("/")
def home():
    products = get_db().execute("SELECT products.*, vendors.store_name AS vendor_name FROM products JOIN vendors ON vendors.id = products.vendor_id WHERE products.status = 'approved' AND vendors.status = 'approved' ORDER BY products.id DESC").fetchall()
    return render_template("index.html", products=products)


@app.route("/auth", methods=["GET", "POST"])
def auth():
    if request.method == "POST":
        action = request.form.get("action")
        username = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password or (action == "register" and not username):
            flash("Please complete all required fields.", "error")
            return render_template("auth.html")
        db = get_db()
        if action == "register":
            try:
                cursor = db.execute("INSERT INTO users (username, email, password_hash, role_id, status, created_at) VALUES (?, ?, ?, ?, 'active', ?)", (username, email, generate_password_hash(password), role_id("customer"), utc_now()))
                db.commit()
                create_session(find_user(email))
                flash("Account created. Welcome to Rijoya!", "success")
                return redirect(url_for("customer_dashboard"))
            except sqlite3.IntegrityError:
                flash("That email or username is already registered.", "error")
        else:
            user = find_user(email)
            if user and user["status"] == "active" and check_password_hash(user["password_hash"], password):
                create_session(user)
                flash("Welcome back!", "success")
                if user["role_name"] in {"admin", "super_admin"}:
                    return redirect(url_for("admin_dashboard"))
                if user["role_name"] == "vendor":
                    return redirect(url_for("vendor_dashboard"))
                return redirect(url_for("customer_dashboard"))
            flash("Email or password is incorrect, or this account is suspended.", "error")
    return render_template("auth.html")


@app.post("/api/auth/login")
def api_login():
    data = request.get_json(silent=True) or request.form
    user = find_user(data.get("email", "").strip().lower())
    if not user or user["status"] != "active" or not check_password_hash(user["password_hash"], data.get("password", "")):
        return jsonify(error="Invalid credentials"), 401
    create_session(user)
    return jsonify(success=True, user_id=user["id"], role=user["role_name"], session_id=session["session_id"])


@app.get("/api/auth/me")
@login_required
def api_me():
    identity = identity_from_session()
    return jsonify(user={"id": identity["user"]["id"], "username": identity["user"]["username"], "email": identity["user"]["email"]}, role=identity["role"], permissions=sorted(identity["permissions"]), last_login=identity["session"]["login_time"])


@app.route("/logout")
def logout():
    destroy_session()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


@app.route("/vendor/register", methods=["GET", "POST"])
def vendor_register():
    if request.method == "POST":
        store_name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not store_name or not email or not password:
            flash("Store name, email, and password are required.", "error")
        else:
            try:
                db = get_db()
                cursor = db.execute("INSERT INTO users (username, email, password_hash, role_id, status, created_at) VALUES (?, ?, ?, ?, 'active', ?)", (store_name, email, generate_password_hash(password), role_id("vendor"), utc_now()))
                db.execute("INSERT INTO vendors (user_id, store_name, email, status) VALUES (?, ?, ?, 'pending')", (cursor.lastrowid, store_name, email))
                db.commit()
                create_session(find_user(email))
                flash("Application submitted. A Super Admin must approve your store before it goes live.", "success")
                return redirect(url_for("vendor_dashboard"))
            except sqlite3.IntegrityError:
                flash("That vendor email or store name is already registered.", "error")
    return render_template("vendor_register.html")


@app.route("/products", methods=["GET", "POST"])
def products():
    if request.method == "POST":
        if not identity_from_session() or identity_from_session()["role"] != "vendor":
            return forbidden("Only vendors can add products from this page.")
        return redirect(url_for("vendor_dashboard"), code=307)
    rows = get_db().execute("SELECT products.*, vendors.store_name AS vendor_name FROM products JOIN vendors ON vendors.id = products.vendor_id WHERE products.status = 'approved' AND vendors.status = 'approved' ORDER BY products.id DESC").fetchall()
    return render_template("products.html", products=rows)


@app.route("/cart")
def cart():
    items = get_cart_items()
    return render_template("cart.html", items=items, total=sum(item["price"] for item in items))


@app.post("/cart/add/<int:product_id>")
def add_to_cart(product_id):
    product = get_db().execute("SELECT products.id FROM products JOIN vendors ON vendors.id = products.vendor_id WHERE products.id = ? AND products.status = 'approved' AND vendors.status = 'approved'", (product_id,)).fetchone()
    if not product:
        flash("Product is not available.", "error")
    else:
        session.setdefault("cart", []).append(product_id)
        session.modified = True
        flash("Product added to your cart.", "success")
    return redirect(request.referrer or url_for("home"))


@app.post("/cart/remove/<int:product_id>")
def remove_from_cart(product_id):
    cart_ids = session.get("cart", [])
    if product_id in cart_ids:
        cart_ids.remove(product_id)
        session.modified = True
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
@role_required("customer")
def checkout():
    items = get_cart_items()
    if not items:
        flash("Your cart is empty.", "error")
        return redirect(url_for("cart"))
    if request.method == "POST":
        db = get_db()
        total = sum(item["price"] for item in items)
        cursor = db.execute("INSERT INTO orders (customer_id, total_amount, status, created_at) VALUES (?, ?, 'confirmed', ?)", (current_user()["id"], total, utc_now()))
        for item in items:
            db.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, 1, ?)", (cursor.lastrowid, item["id"], item["price"]))
        db.commit()
        session["cart"] = []
        flash("Order confirmed. Thank you for shopping with Rijoya!", "success")
        return redirect(url_for("customer_dashboard"))
    return render_template("checkout.html", items=items, total=sum(i["price"] for i in items))


@app.route("/customer/dashboard")
@role_required("customer")
def customer_dashboard():
    db = get_db()
    user = current_user()
    orders = db.execute("SELECT * FROM orders WHERE customer_id = ? ORDER BY id DESC", (user["id"],)).fetchall()
    addresses = db.execute("SELECT * FROM addresses WHERE user_id = ? ORDER BY id DESC", (user["id"],)).fetchall()
    return render_template("customer_dashboard.html", orders=orders, addresses=addresses, user=user)


@app.post("/customer/address")
@role_required("customer")
def customer_address():
    address = request.form.get("address", "").strip()
    if address:
        get_db().execute("INSERT INTO addresses (user_id, address, created_at) VALUES (?, ?, ?)", (current_user()["id"], address, utc_now()))
        get_db().commit()
        flash("Address saved.", "success")
    return redirect(url_for("customer_dashboard"))


@app.route("/vendor/dashboard", methods=["GET", "POST"])
@vendor_required
def vendor_dashboard():
    identity = identity_from_session()
    vendor = identity["vendor"]
    db = get_db()
    if not vendor:
        return forbidden("Your vendor profile is not set up.")
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        price = request.form.get("price", "").strip()
        if not name or not price:
            flash("Product name and price are required.", "error")
        else:
            try:
                db.execute("INSERT INTO products (name, price, vendor_id, status) VALUES (?, ?, ?, 'pending')", (name, float(price), vendor["id"]))
                db.commit()
                flash("Product submitted for approval.", "success")
            except ValueError:
                flash("Price must be a number.", "error")
    products = db.execute("SELECT * FROM products WHERE vendor_id = ? ORDER BY id DESC", (vendor["id"],)).fetchall()
    orders = db.execute("SELECT orders.id AS order_number, products.name AS product_name, order_items.quantity, order_items.price AS unit_price, (order_items.quantity * order_items.price) AS order_total, orders.status, orders.created_at FROM orders JOIN order_items ON order_items.order_id = orders.id JOIN products ON products.id = order_items.product_id WHERE products.vendor_id = ? ORDER BY orders.id DESC", (vendor["id"],)).fetchall()
    earnings = db.execute("SELECT COALESCE(SUM(order_items.quantity * order_items.price), 0) FROM order_items JOIN products ON products.id = order_items.product_id WHERE products.vendor_id = ?", (vendor["id"],)).fetchone()[0]
    return render_template("vendor_dashboard.html", vendor=vendor, products=products, orders=orders, earnings=earnings)


@app.post("/vendor/product/<int:product_id>/edit")
@vendor_required
def vendor_product_edit(product_id):
    vendor = identity_from_session()["vendor"]
    try:
        get_db().execute("UPDATE products SET name = ?, price = ?, status = 'pending' WHERE id = ? AND vendor_id = ?", (request.form.get("name", "").strip(), float(request.form.get("price", "")), product_id, vendor["id"]))
        get_db().commit()
        flash("Product updated and sent for approval again.", "success")
    except ValueError:
        flash("Price must be a number.", "error")
    return redirect(url_for("vendor_dashboard") + "#products")


@app.post("/vendor/product/<int:product_id>/delete")
@vendor_required
def vendor_product_delete(product_id):
    vendor = identity_from_session()["vendor"]
    db = get_db()
    db.execute("DELETE FROM order_items WHERE product_id = ? AND product_id IN (SELECT id FROM products WHERE vendor_id = ?)", (product_id, vendor["id"]))
    db.execute("DELETE FROM products WHERE id = ? AND vendor_id = ?", (product_id, vendor["id"]))
    db.commit()
    flash("Your product was deleted.", "success")
    return redirect(url_for("vendor_dashboard") + "#products")


@app.post("/vendor/order/<int:order_id>/status")
@vendor_required
def vendor_order_status(order_id):
    vendor = identity_from_session()["vendor"]
    status = request.form.get("status")
    if status not in {"processing", "shipped", "completed"}:
        return forbidden("Vendors can only move orders to processing, shipped, or completed.")
    get_db().execute("UPDATE orders SET status = ? WHERE id = ? AND id IN (SELECT order_items.order_id FROM order_items JOIN products ON products.id = order_items.product_id WHERE products.vendor_id = ?)", (status, order_id, vendor["id"]))
    get_db().commit()
    flash(f"Your order was marked {status}.", "success")
    return redirect(url_for("vendor_dashboard") + "#orders")


@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    identity = identity_from_session()
    vendors = db.execute("SELECT vendors.*, users.email FROM vendors JOIN users ON users.id = vendors.user_id ORDER BY vendors.id DESC").fetchall()
    products = db.execute("SELECT products.*, vendors.store_name AS vendor_name FROM products JOIN vendors ON vendors.id = products.vendor_id ORDER BY products.id DESC").fetchall()
    orders = db.execute("SELECT orders.*, users.username AS customer_name FROM orders JOIN users ON users.id = orders.customer_id ORDER BY orders.id DESC").fetchall()
    admins = db.execute("SELECT users.*, roles.name AS role_name FROM users JOIN roles ON roles.id = users.role_id WHERE roles.name = 'admin' ORDER BY users.id DESC").fetchall()
    customers = db.execute("SELECT users.* FROM users JOIN roles ON roles.id = users.role_id WHERE roles.name = 'customer' ORDER BY users.id DESC").fetchall()
    stats = {"users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0], "vendors": db.execute("SELECT COUNT(*) FROM vendors").fetchone()[0], "products": db.execute("SELECT COUNT(*) FROM products").fetchone()[0], "orders": db.execute("SELECT COUNT(*) FROM orders").fetchone()[0], "sales": db.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders").fetchone()[0]}
    tickets = db.execute("SELECT support_tickets.*, users.username FROM support_tickets JOIN users ON users.id = support_tickets.user_id ORDER BY support_tickets.id DESC").fetchall()
    return render_template("admin.html", vendors=vendors, products=products, orders=orders, admins=admins, customers=customers, stats=stats, permissions=sorted(identity["permissions"]), tickets=tickets)


@app.post("/admin/admin/create")
@super_admin_required
def admin_create():
    data = request.form
    try:
        db = get_db()
        db.execute("INSERT INTO users (username, email, password_hash, role_id, status, created_at) VALUES (?, ?, ?, ?, 'active', ?)", (data.get("name", "").strip(), data.get("email", "").strip().lower(), generate_password_hash(data.get("password", "")), role_id("admin"), utc_now()))
        db.commit()
        flash("Admin account created.", "success")
    except sqlite3.IntegrityError:
        flash("That admin email or username is already in use.", "error")
    return redirect(url_for("admin_dashboard") + "#admins")


@app.post("/admin/admin/<int:user_id>/edit")
@super_admin_required
def admin_edit(user_id):
    try:
        get_db().execute("UPDATE users SET username = ?, email = ? WHERE id = ? AND role_id = ?", (request.form.get("name", "").strip(), request.form.get("email", "").strip().lower(), user_id, role_id("admin")))
        get_db().commit()
        flash("Admin account updated.", "success")
    except sqlite3.IntegrityError:
        flash("That admin email or username is already in use.", "error")
    return redirect(url_for("admin_dashboard") + "#admins")


@app.post("/admin/admin/<int:user_id>/status")
@super_admin_required
def admin_status(user_id):
    status = request.form.get("status")
    if status not in {"active", "suspended"}:
        return forbidden("Invalid admin account status.")
    get_db().execute("UPDATE users SET status = ? WHERE id = ? AND role_id = ?", (status, user_id, role_id("admin")))
    get_db().commit()
    flash(f"Admin account marked {status}.", "success")
    return redirect(url_for("admin_dashboard") + "#admins")


@app.post("/admin/admin/<int:user_id>/delete")
@super_admin_required
def admin_delete(user_id):
    db = get_db()
    db.execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ? AND role_id = ?", (user_id, role_id("admin")))
    db.commit()
    flash("Admin account deleted.", "success")
    return redirect(url_for("admin_dashboard") + "#admins")


@app.post("/admin/admin/<int:user_id>/permissions")
@super_admin_required
def admin_permissions(user_id):
    db = get_db()
    db.execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))
    for permission in request.form.getlist("permissions"):
        row = db.execute("SELECT id FROM permissions WHERE name = ?", (permission,)).fetchone()
        if row:
            db.execute("INSERT OR IGNORE INTO user_permissions (user_id, permission_id) VALUES (?, ?)", (user_id, row["id"]))
    db.commit()
    flash("Admin permissions updated.", "success")
    return redirect(url_for("admin_dashboard") + "#admins")


@app.post("/admin/vendor/<int:vendor_id>/status")
@permission_required("manage_vendors")
def admin_vendor_status(vendor_id):
    status = request.form.get("status")
    if status not in {"pending", "approved", "rejected"}:
        return forbidden("Invalid vendor status.")
    get_db().execute("UPDATE vendors SET status = ? WHERE id = ?", (status, vendor_id))
    get_db().commit()
    flash(f"Vendor marked {status}.", "success")
    return redirect(url_for("admin_dashboard") + "#vendors")


@app.post("/admin/vendor/<int:vendor_id>/edit")
@permission_required("manage_vendors")
def admin_vendor_edit(vendor_id):
    try:
        get_db().execute("UPDATE vendors SET store_name = ? WHERE id = ?", (request.form.get("name", "").strip(), vendor_id))
        get_db().commit()
        flash("Vendor updated.", "success")
    except sqlite3.IntegrityError:
        flash("That vendor name is already in use.", "error")
    return redirect(url_for("admin_dashboard") + "#vendors")


@app.post("/admin/vendor/<int:vendor_id>/delete")
@permission_required("manage_vendors")
def admin_vendor_delete(vendor_id):
    db = get_db()
    db.execute("DELETE FROM order_items WHERE product_id IN (SELECT id FROM products WHERE vendor_id = ?)", (vendor_id,))
    db.execute("DELETE FROM products WHERE vendor_id = ?", (vendor_id,))
    db.execute("DELETE FROM vendors WHERE id = ?", (vendor_id,))
    db.commit()
    flash("Vendor and its products were deleted.", "success")
    return redirect(url_for("admin_dashboard") + "#vendors")


@app.post("/admin/product/<int:product_id>/status")
@permission_required("manage_products")
def admin_product_status(product_id):
    status = request.form.get("status")
    if status not in {"pending", "approved", "rejected"}:
        return forbidden("Invalid product status.")
    get_db().execute("UPDATE products SET status = ? WHERE id = ?", (status, product_id))
    get_db().commit()
    flash(f"Product marked {status}.", "success")
    return redirect(url_for("admin_dashboard") + "#products")


@app.post("/admin/product/<int:product_id>/edit")
@permission_required("manage_products")
def admin_product_edit(product_id):
    try:
        get_db().execute("UPDATE products SET name = ?, price = ? WHERE id = ?", (request.form.get("name", "").strip(), float(request.form.get("price", "")), product_id))
        get_db().commit()
        flash("Product updated.", "success")
    except ValueError:
        flash("Price must be a number.", "error")
    return redirect(url_for("admin_dashboard") + "#products")


@app.post("/admin/product/<int:product_id>/delete")
@permission_required("manage_products")
def admin_product_delete(product_id):
    db = get_db()
    db.execute("DELETE FROM order_items WHERE product_id = ?", (product_id,))
    db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    db.commit()
    flash("Product deleted.", "success")
    return redirect(url_for("admin_dashboard") + "#products")


@app.post("/admin/order/<int:order_id>/status")
@permission_required("manage_orders")
def admin_order_status(order_id):
    status = request.form.get("status")
    if status not in {"pending", "confirmed", "processing", "shipped", "completed", "cancelled"}:
        return forbidden("Invalid order status.")
    get_db().execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    get_db().commit()
    flash(f"Order marked {status}.", "success")
    return redirect(url_for("admin_dashboard") + "#orders")


@app.post("/admin/support/<int:ticket_id>/status")
@permission_required("manage_support")
def admin_support_status(ticket_id):
    status = request.form.get("status")
    if status not in {"open", "in_progress", "closed"}:
        return forbidden("Invalid support status.")
    get_db().execute("UPDATE support_tickets SET status = ? WHERE id = ?", (status, ticket_id))
    get_db().commit()
    flash("Support ticket updated.", "success")
    return redirect(url_for("admin_dashboard") + "#support")


@app.cli.command("init-db")
def init_db_command():
    init_db()
    print("Initialized the Rijoya SQLite database.")


if __name__ == "__main__":
    if not DATABASE.exists():
        init_db()
    app.run(debug=True)
