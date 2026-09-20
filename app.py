from pathlib import Path
import sqlite3
from functools import wraps
from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "rijoya.db"
SCHEMA = BASE_DIR / "schema.sql"

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key"
app.config["DATABASE"] = DATABASE


def get_db():
    if "db" not in g:
        if not Path(app.config["DATABASE"]).exists():
            init_db()
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(app.config["DATABASE"])
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA.read_text())
    db.execute(
        "UPDATE users SET password = ?, is_admin = 1 WHERE email = ?",
        (generate_password_hash("admin123"), "admin@rijoya.local"),
    )
    db.commit()
    db.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("auth"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in as a super admin first.", "error")
            return redirect(url_for("auth"))
        if not session.get("is_admin"):
            flash("Super admin access is required.", "error")
            return redirect(url_for("home"))
        return view(*args, **kwargs)
    return wrapped


def get_cart_items():
    ids = session.get("cart", [])
    if not ids:
        return []
    marks = ",".join("?" for _ in ids)
    return get_db().execute(
        f"SELECT products.*, vendors.name AS vendor_name FROM products "
        f"JOIN vendors ON vendors.id = products.vendor_id "
        f"WHERE products.id IN ({marks}) AND products.status = 'approved' AND vendors.status = 'approved'",
        ids,
    ).fetchall()


@app.context_processor
def shared_template_data():
    return {
        "cart_count": len(session.get("cart", [])),
        "current_user": session.get("user_name"),
        "is_admin": session.get("is_admin", False),
    }


@app.route("/")
def home():
    products = get_db().execute(
        "SELECT products.*, vendors.name AS vendor_name FROM products "
        "JOIN vendors ON vendors.id = products.vendor_id "
        "WHERE products.status = 'approved' AND vendors.status = 'approved' "
        "ORDER BY products.id DESC"
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
                    "INSERT INTO users (name, email, password, is_admin) VALUES (?, ?, ?, 0)",
                    (name, email, generate_password_hash(password)),
                )
                db.commit()
                session.update(user_id=cursor.lastrowid, user_name=name, is_admin=False)
                flash("Account created. Welcome to Rijoya!", "success")
                return redirect(url_for("home"))
            except sqlite3.IntegrityError:
                flash("That email is already registered.", "error")
        else:
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if user and check_password_hash(user["password"], password):
                session.update(user_id=user["id"], user_name=user["name"], is_admin=bool(user["is_admin"]))
                flash("Welcome back!", "success")
                return redirect(url_for("admin_dashboard" if user["is_admin"] else "home"))
            flash("Email or password is incorrect.", "error")
    return render_template("auth.html")


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
        if not name or not email:
            flash("Shop name and email are required.", "error")
        else:
            try:
                cursor = get_db().execute(
                    "INSERT INTO vendors (name, email, products, status) VALUES (?, ?, ?, 'pending')",
                    (name, email, ""),
                )
                get_db().commit()
                session["vendor_id"] = cursor.lastrowid
                session["vendor_name"] = name
                flash("Application submitted. A super admin must approve your shop before it goes live.", "success")
                return redirect(url_for("products"))
            except sqlite3.IntegrityError:
                flash("That vendor email is already registered.", "error")
    return render_template("vendor_register.html")


@app.route("/products", methods=["GET", "POST"])
def products():
    if request.method == "POST":
        vendor_id = session.get("vendor_id")
        if not vendor_id:
            flash("Register as a vendor before uploading products.", "error")
            return redirect(url_for("vendor_register"))
        name = request.form.get("name", "").strip()
        price = request.form.get("price", "").strip()
        if not name or not price:
            flash("Product name and price are required.", "error")
        else:
            try:
                get_db().execute(
                    "INSERT INTO products (name, price, vendor_id, status) VALUES (?, ?, ?, 'pending')",
                    (name, float(price), vendor_id),
                )
                get_db().commit()
                flash("Product submitted for admin approval.", "success")
                return redirect(url_for("products"))
            except ValueError:
                flash("Price must be a number.", "error")
    rows = get_db().execute(
        "SELECT products.*, vendors.name AS vendor_name FROM products "
        "JOIN vendors ON vendors.id = products.vendor_id ORDER BY products.id DESC"
    ).fetchall()
    return render_template("products.html", products=rows)


@app.route("/cart")
def cart():
    items = get_cart_items()
    total = sum(item["price"] for item in items)
    return render_template("cart.html", items=items, total=total)


@app.route("/cart/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    product = get_db().execute(
        "SELECT products.id FROM products JOIN vendors ON vendors.id = products.vendor_id "
        "WHERE products.id = ? AND products.status = 'approved' AND vendors.status = 'approved'",
        (product_id,),
    ).fetchone()
    if not product:
        flash("Product is not available.", "error")
    else:
        cart_ids = session.setdefault("cart", [])
        cart_ids.append(product_id)
        session.modified = True
        flash("Product added to your cart.", "success")
    return redirect(request.referrer or url_for("home"))


@app.route("/cart/remove/<int:product_id>", methods=["POST"])
def remove_from_cart(product_id):
    cart_ids = session.get("cart", [])
    if product_id in cart_ids:
        cart_ids.remove(product_id)
        session.modified = True
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    items = get_cart_items()
    if not items:
        flash("Your cart is empty.", "error")
        return redirect(url_for("cart"))
    if request.method == "POST":
        db = get_db()
        for item in items:
            db.execute(
                "INSERT INTO orders (user_id, product_id, status) VALUES (?, ?, 'confirmed')",
                (session["user_id"], item["id"]),
            )
        db.commit()
        session["cart"] = []
        flash("Order confirmed. Thank you for shopping with Rijoya!", "success")
        return redirect(url_for("home"))
    return render_template("checkout.html", items=items, total=sum(i["price"] for i in items))


@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    vendors = db.execute("SELECT * FROM vendors ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END, id DESC").fetchall()
    products = db.execute(
        "SELECT products.*, vendors.name AS vendor_name FROM products "
        "JOIN vendors ON vendors.id = products.vendor_id ORDER BY products.id DESC"
    ).fetchall()
    orders = db.execute(
        "SELECT orders.*, users.name AS customer_name, products.name AS product_name "
        "FROM orders JOIN users ON users.id = orders.user_id "
        "JOIN products ON products.id = orders.product_id ORDER BY orders.id DESC"
    ).fetchall()
    stats = {
        "vendors": db.execute("SELECT COUNT(*) FROM vendors").fetchone()[0],
        "pending_vendors": db.execute("SELECT COUNT(*) FROM vendors WHERE status = 'pending'").fetchone()[0],
        "products": db.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "pending_products": db.execute("SELECT COUNT(*) FROM products WHERE status = 'pending'").fetchone()[0],
        "orders": db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
    }
    return render_template("admin.html", vendors=vendors, products=products, orders=orders, stats=stats)


@app.route("/admin/vendor/<int:vendor_id>/status", methods=["POST"])
@admin_required
def admin_vendor_status(vendor_id):
    status = request.form.get("status")
    if status not in {"pending", "approved", "rejected"}:
        flash("Invalid vendor status.", "error")
    else:
        get_db().execute("UPDATE vendors SET status = ? WHERE id = ?", (status, vendor_id))
        get_db().commit()
        flash(f"Vendor marked {status}.", "success")
    return redirect(url_for("admin_dashboard") + "#vendors")


@app.route("/admin/vendor/<int:vendor_id>/edit", methods=["POST"])
@admin_required
def admin_vendor_edit(vendor_id):
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    if not name or not email:
        flash("Vendor name and email are required.", "error")
    else:
        try:
            get_db().execute("UPDATE vendors SET name = ?, email = ? WHERE id = ?", (name, email, vendor_id))
            get_db().commit()
            flash("Vendor updated.", "success")
        except sqlite3.IntegrityError:
            flash("That vendor email is already in use.", "error")
    return redirect(url_for("admin_dashboard") + "#vendors")


@app.route("/admin/vendor/<int:vendor_id>/delete", methods=["POST"])
@admin_required
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


@app.route("/admin/product/<int:product_id>/status", methods=["POST"])
@admin_required
def admin_product_status(product_id):
    status = request.form.get("status")
    if status not in {"pending", "approved", "rejected"}:
        flash("Invalid product status.", "error")
    else:
        get_db().execute("UPDATE products SET status = ? WHERE id = ?", (status, product_id))
        get_db().commit()
        flash(f"Product marked {status}.", "success")
    return redirect(url_for("admin_dashboard") + "#products")


@app.route("/admin/product/<int:product_id>/edit", methods=["POST"])
@admin_required
def admin_product_edit(product_id):
    name = request.form.get("name", "").strip()
    price = request.form.get("price", "").strip()
    if not name or not price:
        flash("Product name and price are required.", "error")
    else:
        try:
            get_db().execute("UPDATE products SET name = ?, price = ? WHERE id = ?", (name, float(price), product_id))
            get_db().commit()
            flash("Product updated.", "success")
        except ValueError:
            flash("Price must be a number.", "error")
    return redirect(url_for("admin_dashboard") + "#products")


@app.route("/admin/product/<int:product_id>/delete", methods=["POST"])
@admin_required
def admin_product_delete(product_id):
    db = get_db()
    db.execute("DELETE FROM orders WHERE product_id = ?", (product_id,))
    db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    db.commit()
    flash("Product deleted.", "success")
    return redirect(url_for("admin_dashboard") + "#products")


@app.route("/admin/order/<int:order_id>/status", methods=["POST"])
@admin_required
def admin_order_status(order_id):
    status = request.form.get("status")
    allowed = {"pending", "confirmed", "processing", "shipped", "completed", "cancelled"}
    if status not in allowed:
        flash("Invalid order status.", "error")
    else:
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
