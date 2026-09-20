from pathlib import Path
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "rijoya.db"
SCHEMA = BASE_DIR / "schema.sql"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", app.config["SECRET_KEY"])
app.config["DATABASE"] = DATABASE
JWT_EXPIRY_HOURS = 8


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
    table = db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'roles'").fetchone()
    db.close()
    return table is None


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
    }.items():
        db.execute(
            "UPDATE users SET password = ?, status = 'active' WHERE email = ?",
            (generate_password_hash(password), email),
        )
    db.commit()
    db.close()


def role_id(name):
    row = get_db().execute("SELECT id FROM roles WHERE name = ?", (name,)).fetchone()
    return row["id"]


def create_access_token(user):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user["id"]),
        "role": user["role_name"],
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, app.config["JWT_SECRET_KEY"], algorithm="HS256")


def bearer_token():
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    return session.get("access_token")


def current_identity():
    if hasattr(g, "identity"):
        return g.identity
    token = bearer_token()
    if not token:
        return None
    try:
        claims = jwt.decode(token, app.config["JWT_SECRET_KEY"], algorithms=["HS256"])
        user = get_db().execute(
            "SELECT users.*, roles.name AS role_name FROM users JOIN roles ON roles.id = users.role_id "
            "WHERE users.id = ? AND users.status = 'active'",
            (int(claims["sub"]),),
        ).fetchone()
        if not user:
            return None
        permissions = {row["name"] for row in get_db().execute(
            "SELECT permissions.name FROM permissions "
            "JOIN role_permissions ON role_permissions.permission_id = permissions.id "
            "WHERE role_permissions.role_id = ?",
            (user["role_id"],),
        ).fetchall()}
        permissions.update(row["name"] for row in get_db().execute(
            "SELECT permissions.name FROM permissions "
            "JOIN user_permissions ON user_permissions.permission_id = permissions.id "
            "WHERE user_permissions.user_id = ?",
            (user["id"],),
        ).fetchall())
        if user["role_name"] == "super_admin":
            permissions = {"*"}
        vendor = get_db().execute("SELECT id, name, status FROM vendors WHERE owner_user_id = ?", (user["id"],)).fetchone()
        g.identity = {"user": user, "role": user["role_name"], "permissions": permissions, "vendor": vendor}
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        g.identity = None
    return g.identity


def is_api_request():
    return request.path.startswith("/api/") or request.is_json


def unauthorized():
    if is_api_request():
        return jsonify(error="Authentication required"), 401
    flash("Please log in first.", "error")
    return redirect(url_for("auth"))


def forbidden(message="You do not have permission to perform this action."):
    if is_api_request():
        return jsonify(error=message), 403
    flash(message, "error")
    return redirect(request.referrer or url_for("home"))


def auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_identity():
            return unauthorized()
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            identity = current_identity()
            if not identity:
                return unauthorized()
            if identity["role"] == "super_admin" or identity["role"] in roles:
                return view(*args, **kwargs)
            return forbidden("Your role cannot access this area.")
        return wrapped
    return decorator


def permission_required(permission):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            identity = current_identity()
            if not identity:
                return unauthorized()
            if identity["role"] == "super_admin" or permission in identity["permissions"]:
                return view(*args, **kwargs)
            return forbidden(f"The '{permission}' permission is required.")
        return wrapped
    return decorator


def super_admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        identity = current_identity()
        if not identity:
            return unauthorized()
        if identity["role"] != "super_admin":
            return forbidden("Super Admin access is required.")
        return view(*args, **kwargs)
    return wrapped


def login_user(user):
    token = create_access_token(user)
    session.clear()
    session.update(
        user_id=user["id"], user_name=user["name"], role=user["role_name"],
        is_admin=user["role_name"] in {"admin", "super_admin"}, access_token=token,
    )
    return token


def find_user(email):
    return get_db().execute(
        "SELECT users.*, roles.name AS role_name FROM users JOIN roles ON roles.id = users.role_id WHERE users.email = ?",
        (email,),
    ).fetchone()


def get_cart_items():
    ids = session.get("cart", [])
    if not ids:
        return []
    marks = ",".join("?" for _ in ids)
    return get_db().execute(
        f"SELECT products.*, vendors.name AS vendor_name FROM products JOIN vendors ON vendors.id = products.vendor_id "
        f"WHERE products.id IN ({marks}) AND products.status = 'approved' AND vendors.status = 'approved'", ids,
    ).fetchall()


@app.context_processor
def shared_template_data():
    identity = current_identity()
    return {
        "cart_count": len(session.get("cart", [])),
        "current_user": identity["user"]["name"] if identity else None,
        "current_role": identity["role"] if identity else None,
        "is_admin": bool(identity and identity["role"] in {"admin", "super_admin"}),
        "is_super_admin": bool(identity and identity["role"] == "super_admin"),
        "is_vendor": bool(identity and identity["role"] == "vendor"),
    }


@app.route("/")
def home():
    products = get_db().execute(
        "SELECT products.*, vendors.name AS vendor_name FROM products JOIN vendors ON vendors.id = products.vendor_id "
        "WHERE products.status = 'approved' AND vendors.status = 'approved' ORDER BY products.id DESC"
    ).fetchall()
    return render_template("index.html", products=products)


@app.route("/auth", methods=["GET", "POST"])
def auth():
    if request.method == "POST":
        action = request.form.get("action")
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password or (action == "register" and not name):
            flash("Please complete all required fields.", "error")
            return render_template("auth.html")
        db = get_db()
        if action == "register":
            try:
                cursor = db.execute(
                    "INSERT INTO users (name, email, password, role_id, status) VALUES (?, ?, ?, ?, 'active')",
                    (name, email, generate_password_hash(password), role_id("customer")),
                )
                db.commit()
                user = find_user(email)
                login_user(user)
                flash("Account created. Welcome to Rijoya!", "success")
                return redirect(url_for("home"))
            except sqlite3.IntegrityError:
                flash("That email is already registered.", "error")
        else:
            user = find_user(email)
            if user and user["status"] == "active" and check_password_hash(user["password"], password):
                login_user(user)
                flash("Welcome back!", "success")
                if user["role_name"] in {"admin", "super_admin"}:
                    return redirect(url_for("admin_dashboard"))
                if user["role_name"] == "vendor":
                    return redirect(url_for("vendor_dashboard"))
                return redirect(url_for("home"))
            flash("Email or password is incorrect, or this account is suspended.", "error")
    return render_template("auth.html")


@app.post("/api/auth/login")
def api_login():
    data = request.get_json(silent=True) or request.form
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    user = find_user(email)
    if not user or user["status"] != "active" or not check_password_hash(user["password"], password):
        return jsonify(error="Invalid credentials"), 401
    token = create_access_token(user)
    return jsonify(access_token=token, token_type="Bearer", expires_in=JWT_EXPIRY_HOURS * 3600, role=user["role_name"])


@app.get("/api/auth/me")
@auth_required
def api_me():
    identity = current_identity()
    return jsonify(user=dict(identity["user"]), role=identity["role"], permissions=sorted(identity["permissions"]))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


@app.route("/vendor/register", methods=["GET", "POST"])
def vendor_register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "vendor123")
        if not name or not email or not password:
            flash("Shop name, email, and password are required.", "error")
        else:
            try:
                db = get_db()
                user = current_identity()
                if user and user["role"] not in {"customer", "vendor"}:
                    return forbidden("Admin accounts cannot register as vendors.")
                if user and user["role"] == "customer":
                    return forbidden("Log out before creating a separate vendor account.")
                cursor = db.execute(
                    "INSERT INTO users (name, email, password, role_id, status) VALUES (?, ?, ?, ?, 'active')",
                    (name, email, generate_password_hash(password), role_id("vendor")),
                )
                vendor_cursor = db.execute(
                    "INSERT INTO vendors (name, email, products, status, owner_user_id) VALUES (?, ?, ?, 'pending', ?)",
                    (name, email, "", cursor.lastrowid),
                )
                db.commit()
                login_user(find_user(email))
                session["vendor_id"] = vendor_cursor.lastrowid
                session["vendor_name"] = name
                flash("Application submitted. A Super Admin must approve your shop before it goes live.", "success")
                return redirect(url_for("vendor_dashboard"))
            except sqlite3.IntegrityError:
                flash("That vendor email is already registered.", "error")
    return render_template("vendor_register.html")


@app.route("/vendor/dashboard", methods=["GET", "POST"])
@role_required("vendor")
def vendor_dashboard():
    identity = current_identity()
    vendor = identity["vendor"]
    if not vendor:
        return forbidden("Your vendor profile is not set up.")
    db = get_db()
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
    orders = db.execute(
        "SELECT orders.*, products.name AS product_name, users.name AS customer_name FROM orders "
        "JOIN products ON products.id = orders.product_id JOIN users ON users.id = orders.user_id "
        "WHERE products.vendor_id = ? ORDER BY orders.id DESC", (vendor["id"],)
    ).fetchall()
    return render_template("vendor_dashboard.html", vendor=vendor, products=products, orders=orders)


@app.post("/vendor/product/<int:product_id>/edit")
@role_required("vendor")
def vendor_product_edit(product_id):
    vendor = current_identity()["vendor"]
    try:
        get_db().execute("UPDATE products SET name = ?, price = ?, status = 'pending' WHERE id = ? AND vendor_id = ?", (request.form.get("name", "").strip(), float(request.form.get("price", "")), product_id, vendor["id"]))
        get_db().commit()
        flash("Product updated and sent for approval again.", "success")
    except ValueError:
        flash("Price must be a number.", "error")
    return redirect(url_for("vendor_dashboard") + "#products")


@app.post("/vendor/product/<int:product_id>/delete")
@role_required("vendor")
def vendor_product_delete(product_id):
    vendor = current_identity()["vendor"]
    db = get_db()
    db.execute("DELETE FROM orders WHERE product_id = ? AND product_id IN (SELECT id FROM products WHERE vendor_id = ?)", (product_id, vendor["id"]))
    db.execute("DELETE FROM products WHERE id = ? AND vendor_id = ?", (product_id, vendor["id"]))
    db.commit()
    flash("Your product was deleted.", "success")
    return redirect(url_for("vendor_dashboard") + "#products")


@app.post("/vendor/order/<int:order_id>/status")
@role_required("vendor")
def vendor_order_status(order_id):
    vendor = current_identity()["vendor"]
    status = request.form.get("status")
    if status not in {"processing", "shipped", "completed"}:
        return forbidden("Vendors can only move orders to processing, shipped, or completed.")
    get_db().execute("UPDATE orders SET status = ? WHERE id = ? AND product_id IN (SELECT id FROM products WHERE vendor_id = ?)", (status, order_id, vendor["id"]))
    get_db().commit()
    flash(f"Your order was marked {status}.", "success")
    return redirect(url_for("vendor_dashboard") + "#orders")


@app.route("/products", methods=["GET", "POST"])
def products():
    if request.method == "POST":
        identity = current_identity()
        if not identity or identity["role"] != "vendor":
            return forbidden("Only vendors can add products from this page.")
        return redirect(url_for("vendor_dashboard"), code=307)
    rows = get_db().execute(
        "SELECT products.*, vendors.name AS vendor_name FROM products JOIN vendors ON vendors.id = products.vendor_id "
        "WHERE products.status = 'approved' AND vendors.status = 'approved' ORDER BY products.id DESC"
    ).fetchall()
    return render_template("products.html", products=rows)


@app.route("/cart")
def cart():
    items = get_cart_items()
    return render_template("cart.html", items=items, total=sum(item["price"] for item in items))


@app.post("/cart/add/<int:product_id>")
def add_to_cart(product_id):
    product = get_db().execute(
        "SELECT products.id FROM products JOIN vendors ON vendors.id = products.vendor_id WHERE products.id = ? "
        "AND products.status = 'approved' AND vendors.status = 'approved'", (product_id,)
    ).fetchone()
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
        for item in items:
            db.execute("INSERT INTO orders (user_id, product_id, status) VALUES (?, ?, 'confirmed')", (current_identity()["user"]["id"], item["id"]))
        db.commit()
        session["cart"] = []
        flash("Order confirmed. Thank you for shopping with Rijoya!", "success")
        return redirect(url_for("home"))
    return render_template("checkout.html", items=items, total=sum(i["price"] for i in items))


@app.route("/admin")
@permission_required("view_dashboard")
def admin_dashboard():
    db = get_db()
    identity = current_identity()
    vendors = db.execute("SELECT * FROM vendors ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END, id DESC").fetchall()
    products = db.execute("SELECT products.*, vendors.name AS vendor_name FROM products JOIN vendors ON vendors.id = products.vendor_id ORDER BY products.id DESC").fetchall()
    orders = db.execute("SELECT orders.*, users.name AS customer_name, products.name AS product_name FROM orders JOIN users ON users.id = orders.user_id JOIN products ON products.id = orders.product_id ORDER BY orders.id DESC").fetchall()
    admins = db.execute("SELECT users.*, roles.name AS role_name FROM users JOIN roles ON roles.id = users.role_id WHERE roles.name = 'admin' ORDER BY users.id DESC").fetchall()
    stats = {
        "vendors": db.execute("SELECT COUNT(*) FROM vendors").fetchone()[0],
        "pending_vendors": db.execute("SELECT COUNT(*) FROM vendors WHERE status = 'pending'").fetchone()[0],
        "products": db.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "pending_products": db.execute("SELECT COUNT(*) FROM products WHERE status = 'pending'").fetchone()[0],
        "orders": db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
    }
    return render_template("admin.html", vendors=vendors, products=products, orders=orders, admins=admins, stats=stats, permissions=sorted(identity["permissions"]))


@app.post("/admin/admin/create")
@super_admin_required
def admin_create():
    data = request.form
    try:
        db = get_db()
        db.execute("INSERT INTO users (name, email, password, role_id, status) VALUES (?, ?, ?, ?, 'active')", (data.get("name", "").strip(), data.get("email", "").strip().lower(), generate_password_hash(data.get("password", "")), role_id("admin")))
        db.commit()
        flash("Admin account created.", "success")
    except sqlite3.IntegrityError:
        flash("That admin email is already in use.", "error")
    return redirect(url_for("admin_dashboard") + "#admins")


@app.post("/admin/admin/<int:user_id>/edit")
@super_admin_required
def admin_edit(user_id):
    try:
        get_db().execute("UPDATE users SET name = ?, email = ? WHERE id = ? AND role_id = ?", (request.form.get("name", "").strip(), request.form.get("email", "").strip().lower(), user_id, role_id("admin")))
        get_db().commit()
        flash("Admin account updated.", "success")
    except sqlite3.IntegrityError:
        flash("That admin email is already in use.", "error")
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
            db.execute("INSERT INTO user_permissions (user_id, permission_id) VALUES (?, ?)", (user_id, row["id"]))
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
        get_db().execute("UPDATE vendors SET name = ?, email = ? WHERE id = ?", (request.form.get("name", "").strip(), request.form.get("email", "").strip().lower(), vendor_id))
        get_db().commit()
        flash("Vendor updated.", "success")
    except sqlite3.IntegrityError:
        flash("That vendor email is already in use.", "error")
    return redirect(url_for("admin_dashboard") + "#vendors")


@app.post("/admin/vendor/<int:vendor_id>/delete")
@permission_required("manage_vendors")
def admin_vendor_delete(vendor_id):
    db = get_db()
    product_ids = [row[0] for row in db.execute("SELECT id FROM products WHERE vendor_id = ?", (vendor_id,)).fetchall()]
    for product_id in product_ids:
        db.execute("DELETE FROM orders WHERE product_id = ?", (product_id,))
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
    db.execute("DELETE FROM orders WHERE product_id = ?", (product_id,))
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


@app.cli.command("init-db")
def init_db_command():
    init_db()
    print("Initialized the Rijoya SQLite database.")


if __name__ == "__main__":
    if not DATABASE.exists():
        init_db()
    app.run(debug=True)
