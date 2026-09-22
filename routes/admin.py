from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _app_helpers():
    from app import get_db, permission_required, role_id, super_admin_required, utc_now
    return locals()


def _permission_required(permission):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            return _app_helpers()["permission_required"](permission)(view)(*args, **kwargs)
        return wrapped
    return decorator


def _super_admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        return _app_helpers()["super_admin_required"](view)(*args, **kwargs)
    return wrapped


@admin_bp.get("")
@_permission_required("view_dashboard")
def dashboard():
    db = _app_helpers()["get_db"]()
    vendors = db.execute("SELECT vendors.*, users.email FROM vendors JOIN users ON users.id = vendors.user_id ORDER BY vendors.id DESC").fetchall()
    products = db.execute("SELECT products.*, vendors.store_name AS vendor_name FROM products JOIN vendors ON vendors.id = products.vendor_id ORDER BY products.id DESC").fetchall()
    orders = db.execute("SELECT orders.*, users.username AS customer_name FROM orders JOIN users ON users.id = orders.customer_id ORDER BY orders.id DESC").fetchall()
    admins = db.execute("SELECT users.*, roles.name AS role_name FROM users JOIN roles ON roles.id = users.role_id WHERE roles.name = 'admin' ORDER BY users.id DESC").fetchall()
    customers = db.execute("SELECT users.* FROM users JOIN roles ON roles.id = users.role_id WHERE roles.name = 'customer' ORDER BY users.id DESC").fetchall()
    tickets = db.execute("SELECT support_tickets.*, users.username FROM support_tickets JOIN users ON users.id = support_tickets.user_id ORDER BY support_tickets.id DESC").fetchall()
    stats = {"users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0], "vendors": db.execute("SELECT COUNT(*) FROM vendors").fetchone()[0], "products": db.execute("SELECT COUNT(*) FROM products").fetchone()[0], "orders": db.execute("SELECT COUNT(*) FROM orders").fetchone()[0], "sales": db.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders").fetchone()[0]}
    return render_template("admin/dashboard.html", vendors=vendors, products=products, orders=orders, admins=admins, customers=customers, tickets=tickets, stats=stats)


@admin_bp.post("/admin/create")
@_super_admin_required
def admin_create():
    helpers = _app_helpers()
    data = request.form
    try:
        db = helpers["get_db"]()
        db.execute("INSERT INTO users (username, email, password_hash, role_id, status, created_at) VALUES (?, ?, ?, ?, 'active', ?)", (data.get("name", "").strip(), data.get("email", "").strip().lower(), generate_password_hash(data.get("password", "")), helpers["role_id"]("admin"), helpers["utc_now"]()))
        db.commit()
        flash("Admin account created.", "success")
    except Exception:
        flash("That admin email or username is already in use.", "error")
    return redirect(url_for("admin.dashboard") + "#admins")


@admin_bp.post("/admin/<int:user_id>/edit")
@_super_admin_required
def admin_edit(user_id):
    helpers = _app_helpers()
    try:
        db = helpers["get_db"]()
        db.execute("UPDATE users SET username = ?, email = ? WHERE id = ? AND role_id = ?", (request.form.get("name", "").strip(), request.form.get("email", "").strip().lower(), user_id, helpers["role_id"]("admin")))
        db.commit()
        flash("Admin account updated.", "success")
    except Exception:
        flash("That admin email or username is already in use.", "error")
    return redirect(url_for("admin.dashboard") + "#admins")


@admin_bp.post("/admin/<int:user_id>/status")
@_super_admin_required
def admin_status(user_id):
    helpers = _app_helpers()
    status = request.form.get("status")
    if status not in {"active", "suspended"}:
        flash("Invalid admin account status.", "error")
    else:
        db = helpers["get_db"]()
        db.execute("UPDATE users SET status = ? WHERE id = ? AND role_id = ?", (status, user_id, helpers["role_id"]("admin")))
        db.commit()
        flash(f"Admin account marked {status}.", "success")
    return redirect(url_for("admin.dashboard") + "#admins")


@admin_bp.post("/admin/<int:user_id>/delete")
@_super_admin_required
def admin_delete(user_id):
    helpers = _app_helpers()
    db = helpers["get_db"]()
    db.execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ? AND role_id = ?", (user_id, helpers["role_id"]("admin")))
    db.commit()
    flash("Admin account deleted.", "success")
    return redirect(url_for("admin.dashboard") + "#admins")


@admin_bp.post("/admin/<int:user_id>/permissions")
@_super_admin_required
def admin_permissions(user_id):
    db = _app_helpers()["get_db"]()
    db.execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))
    for name in request.form.getlist("permissions"):
        permission = db.execute("SELECT id FROM permissions WHERE name = ?", (name,)).fetchone()
        if permission:
            db.execute("INSERT OR IGNORE INTO user_permissions (user_id, permission_id) VALUES (?, ?)", (user_id, permission["id"]))
    db.commit()
    flash("Admin permissions updated.", "success")
    return redirect(url_for("admin.dashboard") + "#admins")


@admin_bp.post("/vendor/<int:vendor_id>/status")
@_permission_required("manage_vendors")
def vendor_status(vendor_id):
    status = request.form.get("status")
    if status in {"pending", "approved", "rejected"}:
        db = _app_helpers()["get_db"]()
        db.execute("UPDATE vendors SET status = ? WHERE id = ?", (status, vendor_id))
        db.commit()
        flash(f"Vendor marked {status}.", "success")
    return redirect(url_for("admin.dashboard") + "#vendors")


@admin_bp.post("/vendor/<int:vendor_id>/edit")
@_permission_required("manage_vendors")
def vendor_edit(vendor_id):
    db = _app_helpers()["get_db"]()
    db.execute("UPDATE vendors SET store_name = ? WHERE id = ?", (request.form.get("name", "").strip(), vendor_id))
    db.commit()
    flash("Vendor updated.", "success")
    return redirect(url_for("admin.dashboard") + "#vendors")


@admin_bp.post("/vendor/<int:vendor_id>/delete")
@_permission_required("manage_vendors")
def vendor_delete(vendor_id):
    db = _app_helpers()["get_db"]()
    db.execute("DELETE FROM order_items WHERE product_id IN (SELECT id FROM products WHERE vendor_id = ?)", (vendor_id,))
    db.execute("DELETE FROM products WHERE vendor_id = ?", (vendor_id,))
    db.execute("DELETE FROM vendors WHERE id = ?", (vendor_id,))
    db.commit()
    flash("Vendor and its products were deleted.", "success")
    return redirect(url_for("admin.dashboard") + "#vendors")


@admin_bp.post("/product/<int:product_id>/status")
@_permission_required("manage_products")
def product_status(product_id):
    status = request.form.get("status")
    if status in {"pending", "approved", "rejected"}:
        db = _app_helpers()["get_db"]()
        db.execute("UPDATE products SET status = ? WHERE id = ?", (status, product_id))
        db.commit()
        flash(f"Product marked {status}.", "success")
    return redirect(url_for("admin.dashboard") + "#products")


@admin_bp.post("/product/<int:product_id>/edit")
@_permission_required("manage_products")
def product_edit(product_id):
    try:
        db = _app_helpers()["get_db"]()
        db.execute("UPDATE products SET name = ?, price = ? WHERE id = ?", (request.form.get("name", "").strip(), float(request.form.get("price", "")), product_id))
        db.commit()
        flash("Product updated.", "success")
    except ValueError:
        flash("Price must be a number.", "error")
    return redirect(url_for("admin.dashboard") + "#products")


@admin_bp.post("/product/<int:product_id>/delete")
@_permission_required("manage_products")
def product_delete(product_id):
    db = _app_helpers()["get_db"]()
    db.execute("DELETE FROM order_items WHERE product_id = ?", (product_id,))
    db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    db.commit()
    flash("Product deleted.", "success")
    return redirect(url_for("admin.dashboard") + "#products")


@admin_bp.post("/order/<int:order_id>/status")
@_permission_required("manage_orders")
def order_status(order_id):
    status = request.form.get("status")
    if status in {"pending", "confirmed", "processing", "shipped", "completed", "cancelled"}:
        db = _app_helpers()["get_db"]()
        db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        db.commit()
        flash(f"Order marked {status}.", "success")
    return redirect(url_for("admin.dashboard") + "#orders")


@admin_bp.post("/support/<int:ticket_id>/status")
@_permission_required("manage_support")
def support_status(ticket_id):
    status = request.form.get("status")
    if status in {"open", "in_progress", "closed"}:
        db = _app_helpers()["get_db"]()
        db.execute("UPDATE support_tickets SET status = ? WHERE id = ?", (status, ticket_id))
        db.commit()
        flash("Support ticket updated.", "success")
    return redirect(url_for("admin.dashboard") + "#support")
