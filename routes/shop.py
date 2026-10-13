import secrets
from decimal import Decimal
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user
from sqlalchemy import update
from extensions import db
from forms import CheckoutForm
from models.models import CartItem, Category, Customer, Order, OrderItem, Product
from utils.helpers import EGYPT_GOVERNORATES, shipping_fee

bp = Blueprint("shop", __name__)


def cart_rows():
    rows = []
    if current_user.is_authenticated and not current_user.is_admin:
        for item in CartItem.query.filter_by(customer_id=current_user.id).all():
            if item.product and item.product.is_active:
                rows.append({"product": item.product, "quantity": item.quantity, "cart_item_id": item.id})
    else:
        bag = session.get("cart_items", {})
        for raw_id, raw_quantity in bag.items():
            if not str(raw_id).isdigit():
                continue
            product = db.session.get(Product, int(raw_id))
            if product and product.is_active:
                rows.append({"product": product, "quantity": int(raw_quantity), "cart_item_id": int(raw_id)})
    return rows


def cart_subtotal(rows=None):
    rows = rows if rows is not None else cart_rows()
    return sum((row["product"].price * row["quantity"] for row in rows), Decimal("0.00"))


def change_cart(product_id, quantity):
    product = db.session.get(Product, product_id)
    if not product or not product.is_active:
        return False, "المنتج غير متاح حالياً."
    quantity = max(0, min(int(quantity), 20))
    if quantity > product.stock:
        quantity = product.stock
    if current_user.is_authenticated and not current_user.is_admin:
        item = CartItem.query.filter_by(customer_id=current_user.id, product_id=product_id).first()
        if quantity <= 0:
            if item:
                db.session.delete(item)
        elif item:
            item.quantity = quantity
        else:
            db.session.add(CartItem(customer_id=current_user.id, product_id=product_id, quantity=quantity))
        db.session.commit()
    else:
        bag = session.setdefault("cart_items", {})
        if quantity <= 0:
            bag.pop(str(product_id), None)
        else:
            bag[str(product_id)] = quantity
        session.modified = True
    return True, "تم تحديث السلة."


@bp.get("/")
def home():
    categories = Category.query.filter_by(is_active=True).order_by(Category.id).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.is_featured.desc(), Product.created_at.desc()).limit(8).all()
    return render_template("shop/home.html", categories=categories, products=products)


@bp.get("/products")
def products():
    query = Product.query.filter_by(is_active=True)
    category_slug = request.args.get("category", "")
    search = request.args.get("q", "").strip()
    if category_slug:
        category = Category.query.filter_by(slug=category_slug, is_active=True).first_or_404()
        query = query.filter_by(category_id=category.id)
    else:
        category = None
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%") | Product.description.ilike(f"%{search}%"))
    items = query.order_by(Product.is_featured.desc(), Product.name).all()
    return render_template("shop/products.html", products=items, selected_category=category, search=search)


@bp.get("/product/<slug>")
def product_detail(slug):
    product = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
    return render_template("shop/product.html", product=product)


@bp.post("/cart/add/<int:product_id>")
def add_to_cart(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    existing = next((row["quantity"] for row in cart_rows() if row["product"].id == product_id), 0)
    ok, message = change_cart(product_id, existing + int(request.form.get("quantity", 1)))
    flash(message, "success" if ok else "error")
    return redirect(request.referrer or url_for("shop.cart"))


@bp.route("/cart", methods=["GET", "POST"])
def cart():
    if request.method == "POST":
        product_id = request.form.get("product_id", "")
        if product_id.isdigit():
            ok, message = change_cart(int(product_id), request.form.get("quantity", 0))
            flash(message, "success" if ok else "error")
        return redirect(url_for("shop.cart"))
    rows = cart_rows()
    return render_template("shop/cart.html", rows=rows, subtotal=cart_subtotal(rows))


@bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    rows = cart_rows()
    if not rows:
        flash("سلة التسوق فارغة.", "info")
        return redirect(url_for("shop.products"))
    form = CheckoutForm()
    form.governorate.choices = [(gov, gov) for gov in EGYPT_GOVERNORATES]
    if current_user.is_authenticated and not current_user.is_admin and request.method == "GET":
        form.full_name.data = current_user.full_name
        form.email.data = current_user.email
        form.phone.data = current_user.phone
    subtotal = cart_subtotal(rows)
    fee = shipping_fee(form.governorate.data or EGYPT_GOVERNORATES[0], form.city.data or "", form.area.data or "")
    if form.validate_on_submit():
        governorate = form.governorate.data
        fee = shipping_fee(governorate, form.city.data or "", form.area.data or "")
        if fee is None:
            flash("لا يوجد سعر توصيل محدد لهذا العنوان. تواصل معنا لإضافته.", "error")
        else:
            try:
                # Recheck stock within the transaction, decrement atomically, and preserve order-line snapshots.
                for row in rows:
                    product = db.session.get(Product, row["product"].id)
                    qty = int(row["quantity"])
                    if not product or not product.is_active or product.stock < qty:
                        raise ValueError(f"الكمية المتاحة من {row['product'].name} تغيرت. راجع سلتك.")
                    result = db.session.execute(
                        update(Product).where(Product.id == product.id, Product.stock >= qty)
                        .values(stock=Product.stock - qty)
                    )
                    if result.rowcount != 1:
                        raise ValueError(f"الكمية المتاحة من {product.name} تغيرت. راجع سلتك.")
                email = (form.email.data or "").strip().lower()
                if current_user.is_authenticated and not current_user.is_admin:
                    customer = current_user
                else:
                    customer = Customer.query.filter_by(email=email).first() if email else None
                    if not customer:
                        local_email = email or f"guest-{secrets.token_hex(8)}@guest.rijoya.local"
                        customer = Customer(full_name=form.full_name.data.strip(), email=local_email, phone=form.phone.data.strip())
                        customer.set_password(secrets.token_urlsafe(32))
                        db.session.add(customer)
                        db.session.flush()
                order = Order(
                    order_number="PENDING", customer=customer,
                    customer_name=form.full_name.data.strip(), email=email,
                    phone=form.phone.data.strip(), governorate=form.governorate.data,
                    city=(form.city.data or "").strip(), area=(form.area.data or "").strip(),
                    address=form.address.data.strip(), notes=(form.notes.data or "").strip(),
                    subtotal=subtotal, shipping_fee=fee, total=subtotal + fee,
                    payment_method="cod", status="new",
                )
                db.session.add(order)
                db.session.flush()
                order.order_number = f"ORD-{order.created_at:%Y%m%d}-{order.id:06d}"
                for row in rows:
                    product = row["product"]
                    qty = int(row["quantity"])
                    db.session.add(OrderItem(
                        order=order, product_id=product.id, product_name=product.name,
                        sku=product.sku, unit_price=product.price, quantity=qty,
                        line_total=product.price * qty,
                    ))
                db.session.flush()
                if current_user.is_authenticated and not current_user.is_admin:
                    CartItem.query.filter_by(customer_id=current_user.id).delete()
                else:
                    session.pop("cart_items", None)
                    session["last_order"] = order.order_number
                db.session.commit()
                return redirect(url_for("shop.order_confirmation", order_number=order.order_number))
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc), "error")
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Checkout failed")
                flash("تعذر إتمام الطلب الآن. حاول مرة أخرى.", "error")
    return render_template("shop/checkout.html", form=form, rows=rows, subtotal=subtotal, shipping=fee)


@bp.get("/order/<order_number>")
def order_confirmation(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    if not current_user.is_authenticated and session.get("last_order") != order.order_number:
        abort(404)
    if current_user.is_authenticated and not current_user.is_admin and order.customer_id != current_user.id:
        abort(404)
    return render_template("shop/order_confirmation.html", order=order)
