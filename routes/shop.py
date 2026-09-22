from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

shop_bp = Blueprint("shop", __name__)


def _app_helpers():
    from app import current_user, get_cart_items, get_db, role_required, utc_now
    return locals()


def _role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            return _app_helpers()["role_required"](*roles)(view)(*args, **kwargs)
        return wrapped
    return decorator


@shop_bp.get("/")
def home():
    db = _app_helpers()["get_db"]()
    products = db.execute("SELECT products.*, vendors.store_name AS vendor_name FROM products JOIN vendors ON vendors.id = products.vendor_id WHERE products.status = 'approved' AND vendors.status = 'approved' ORDER BY products.id DESC").fetchall()
    return render_template("shop/index.html", products=products)


@shop_bp.get("/products")
def products():
    db = _app_helpers()["get_db"]()
    rows = db.execute("SELECT products.*, vendors.store_name AS vendor_name FROM products JOIN vendors ON vendors.id = products.vendor_id WHERE products.status = 'approved' AND vendors.status = 'approved' ORDER BY products.id DESC").fetchall()
    return render_template("shop/products.html", products=rows)


@shop_bp.get("/cart")
def cart():
    items = _app_helpers()["get_cart_items"]()
    return render_template("shop/cart.html", items=items, total=sum(item["price"] for item in items))


@shop_bp.post("/cart/add/<int:product_id>")
def add_to_cart(product_id):
    db = _app_helpers()["get_db"]()
    product = db.execute("SELECT products.id FROM products JOIN vendors ON vendors.id = products.vendor_id WHERE products.id = ? AND products.status = 'approved' AND vendors.status = 'approved'", (product_id,)).fetchone()
    if product:
        session.setdefault("cart", []).append(product_id)
        session.modified = True
        flash("Product added to your cart.", "success")
    else:
        flash("Product is not available.", "error")
    return redirect(request.referrer or url_for("shop.home"))


@shop_bp.post("/cart/remove/<int:product_id>")
def remove_from_cart(product_id):
    cart_ids = session.get("cart", [])
    if product_id in cart_ids:
        cart_ids.remove(product_id)
        session.modified = True
    return redirect(url_for("shop.cart"))


@shop_bp.route("/checkout", methods=["GET", "POST"])
@_role_required("customer")
def checkout():
    helpers = _app_helpers()
    items = helpers["get_cart_items"]()
    if not items:
        flash("Your cart is empty.", "error")
        return redirect(url_for("shop.cart"))
    if request.method == "POST":
        db = helpers["get_db"]()
        total = sum(item["price"] for item in items)
        order_id = db.execute("INSERT INTO orders (customer_id, total_amount, status, created_at) VALUES (?, ?, 'confirmed', ?)", (helpers["current_user"]()["id"], total, helpers["utc_now"]())).lastrowid
        for item in items:
            db.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, 1, ?)", (order_id, item["id"], item["price"]))
        db.commit()
        session["cart"] = []
        flash("Order confirmed. Thank you for shopping with Rijoya!", "success")
        return redirect(url_for("shop.customer_dashboard"))
    return render_template("shop/checkout.html", items=items, total=sum(item["price"] for item in items))


@shop_bp.get("/customer/dashboard")
@_role_required("customer")
def customer_dashboard():
    helpers = _app_helpers()
    db = helpers["get_db"]()
    user = helpers["current_user"]()
    orders = db.execute("SELECT * FROM orders WHERE customer_id = ? ORDER BY id DESC", (user["id"],)).fetchall()
    addresses = db.execute("SELECT * FROM addresses WHERE user_id = ? ORDER BY id DESC", (user["id"],)).fetchall()
    return render_template("shop/customer_dashboard.html", orders=orders, addresses=addresses, user=user)


@shop_bp.post("/customer/address")
@_role_required("customer")
def customer_address():
    helpers = _app_helpers()
    address = request.form.get("address", "").strip()
    if address:
        db = helpers["get_db"]()
        db.execute("INSERT INTO addresses (user_id, address, created_at) VALUES (?, ?, ?)", (helpers["current_user"]()["id"], address, helpers["utc_now"]()))
        db.commit()
        flash("Address saved.", "success")
    return redirect(url_for("shop.customer_dashboard"))
