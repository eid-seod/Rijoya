import sqlite3
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, url_for

vendor_bp = Blueprint("vendor", __name__, url_prefix="/vendor")


def _app_helpers():
    from app import current_user, get_db, identity_from_session, login_required, role_id, utc_now, vendor_required
    return locals()


def _login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        return _app_helpers()["login_required"](view)(*args, **kwargs)
    return wrapped


def _vendor_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        return _app_helpers()["vendor_required"](view)(*args, **kwargs)
    return wrapped


@vendor_bp.route("/apply", methods=["GET", "POST"])
@_login_required
def apply():
    helpers = _app_helpers()
    user = helpers["current_user"]()
    db = helpers["get_db"]()
    existing = db.execute("SELECT * FROM vendors WHERE user_id = ?", (user["id"],)).fetchone()
    if request.method == "POST":
        store_name = request.form.get("store_name", "").strip()
        if existing:
            flash("You already have a vendor application.", "error")
        elif not store_name:
            flash("Store name is required.", "error")
        else:
            try:
                db.execute("INSERT INTO vendors (user_id, store_name, email, status) VALUES (?, ?, ?, 'pending')", (user["id"], store_name, user["email"]))
                db.commit()
                flash("Your vendor application was submitted for approval.", "success")
                return redirect(url_for("vendor.apply"))
            except sqlite3.IntegrityError:
                flash("That store name is already in use.", "error")
    return render_template("vendor/apply.html", existing=existing, user=user)


@vendor_bp.get("/dashboard")
@_vendor_required
def dashboard():
    helpers = _app_helpers()
    identity = helpers["identity_from_session"]()
    vendor = identity["vendor"]
    db = helpers["get_db"]()
    products = db.execute("SELECT * FROM products WHERE vendor_id = ? ORDER BY id DESC", (vendor["id"],)).fetchall()
    orders = db.execute("SELECT orders.id AS order_number, products.name AS product_name, order_items.quantity, order_items.price AS unit_price, (order_items.quantity * order_items.price) AS order_total, orders.status, orders.created_at FROM orders JOIN order_items ON order_items.order_id = orders.id JOIN products ON products.id = order_items.product_id WHERE products.vendor_id = ? ORDER BY orders.id DESC", (vendor["id"],)).fetchall()
    earnings = db.execute("SELECT COALESCE(SUM(order_items.quantity * order_items.price), 0) FROM order_items JOIN products ON products.id = order_items.product_id WHERE products.vendor_id = ?", (vendor["id"],)).fetchone()[0]
    return render_template("vendor/dashboard.html", vendor=vendor, products=products, orders=orders, earnings=earnings)


@vendor_bp.post("/products/new")
@_vendor_required
def product_new():
    helpers = _app_helpers()
    vendor = helpers["identity_from_session"]()["vendor"]
    name = request.form.get("name", "").strip()
    price = request.form.get("price", "").strip()
    if not name or not price:
        flash("Product name and price are required.", "error")
    else:
        try:
            db = helpers["get_db"]()
            db.execute("INSERT INTO products (name, price, vendor_id, status) VALUES (?, ?, ?, 'pending')", (name, float(price), vendor["id"]))
            db.commit()
            flash("Product submitted for approval.", "success")
        except ValueError:
            flash("Price must be a number.", "error")
    return redirect(url_for("vendor.dashboard") + "#products")


@vendor_bp.post("/product/<int:product_id>/edit")
@_vendor_required
def product_edit(product_id):
    helpers = _app_helpers()
    vendor = helpers["identity_from_session"]()["vendor"]
    try:
        db = helpers["get_db"]()
        db.execute("UPDATE products SET name = ?, price = ?, status = 'pending' WHERE id = ? AND vendor_id = ?", (request.form.get("name", "").strip(), float(request.form.get("price", "")), product_id, vendor["id"]))
        db.commit()
        flash("Product updated and sent for approval again.", "success")
    except ValueError:
        flash("Price must be a number.", "error")
    return redirect(url_for("vendor.dashboard") + "#products")


@vendor_bp.post("/product/<int:product_id>/delete")
@_vendor_required
def product_delete(product_id):
    helpers = _app_helpers()
    vendor = helpers["identity_from_session"]()["vendor"]
    db = helpers["get_db"]()
    db.execute("DELETE FROM order_items WHERE product_id = ? AND product_id IN (SELECT id FROM products WHERE vendor_id = ?)", (product_id, vendor["id"]))
    db.execute("DELETE FROM products WHERE id = ? AND vendor_id = ?", (product_id, vendor["id"]))
    db.commit()
    flash("Your product was deleted.", "success")
    return redirect(url_for("vendor.dashboard") + "#products")


@vendor_bp.post("/order/<int:order_id>/status")
@_vendor_required
def order_status(order_id):
    helpers = _app_helpers()
    vendor = helpers["identity_from_session"]()["vendor"]
    status = request.form.get("status")
    if status not in {"processing", "shipped", "completed"}:
        flash("Invalid vendor order status.", "error")
    else:
        db = helpers["get_db"]()
        db.execute("UPDATE orders SET status = ? WHERE id = ? AND id IN (SELECT order_items.order_id FROM order_items JOIN products ON products.id = order_items.product_id WHERE products.vendor_id = ?)", (status, order_id, vendor["id"]))
        db.commit()
        flash(f"Your order was marked {status}.", "success")
    return redirect(url_for("vendor.dashboard") + "#orders")
