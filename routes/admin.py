import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import wraps
from uuid import uuid4
from flask import Blueprint, abort, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import update
from extensions import db
from forms import CategoryForm, LoginForm, ProductForm
from models.models import Admin, Category, Customer, Order, Product, ShippingRate
from utils.helpers import EGYPT_GOVERNORATES, save_image, slugify

bp = Blueprint("admin", __name__, url_prefix="/admin")
ORDER_STATUSES = ["new", "confirmed", "preparing", "shipped", "delivered", "cancelled"]
STATUS_LABELS = {"new": "جديد", "confirmed": "مؤكد", "preparing": "قيد التجهيز", "shipped": "تم الشحن", "delivered": "تم التسليم", "cancelled": "ملغي"}


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        admin = Admin.query.filter_by(email=form.email.data.strip().lower()).first()
        if admin and admin.check_password(form.password.data):
            login_user(admin, remember=form.remember.data)
            return redirect(url_for("admin.dashboard"))
        flash("بيانات دخول المشرف غير صحيحة.", "error")
    return render_template("admin/login.html", form=form)


@bp.post("/logout")
@admin_required
def logout():
    logout_user()
    return redirect(url_for("admin.login"))


@bp.get("/")
@admin_required
def dashboard():
    return render_template("admin/dashboard.html", product_count=Product.query.count(),
        order_count=Order.query.count(), pending_count=Order.query.filter(Order.status.in_(["new", "confirmed", "preparing"])).count(),
        customer_count=Customer.query.count(), recent_orders=Order.query.order_by(Order.created_at.desc()).limit(8).all(),
        status_labels=STATUS_LABELS)


@bp.get("/products")
@admin_required
def products():
    items = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("admin/products.html", products=items)


def _product_choices(form):
    form.category_id.choices = [(0, "بدون تصنيف")] + [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]


@bp.route("/products/new", methods=["GET", "POST"])
@bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def product_form(product_id=None):
    product = db.session.get(Product, product_id) if product_id else Product()
    if product_id and not product:
        abort(404)
    form = ProductForm(obj=product)
    _product_choices(form)
    if request.method == "GET" and product_id:
        form.category_id.data = product.category_id or 0
    if form.validate_on_submit():
        existing_sku = Product.query.filter(Product.sku == form.sku.data.strip(), Product.id != (product.id or 0)).first()
        if existing_sku:
            flash("رمز SKU مستخدم من قبل.", "error")
        else:
            product.name = form.name.data.strip()
            product.slug = slugify(product.name)
            if Product.query.filter(Product.slug == product.slug, Product.id != (product.id or 0)).first():
                product.slug = f"{product.slug}-{product.id or 'new'}-{int(datetime.utcnow().timestamp())}"
            product.category_id = form.category_id.data or None
            product.sku = form.sku.data.strip()
            product.description = form.description.data or ""
            product.price = form.price.data
            product.compare_at_price = form.compare_at_price.data
            product.stock = form.stock.data
            product.is_active = form.is_active.data
            product.is_featured = form.is_featured.data
            if form.image.data:
                try:
                    product.image = save_image(form.image.data)
                except ValueError as exc:
                    flash(str(exc), "error")
                    return render_template("admin/product_form.html", form=form, product=product)
            db.session.add(product)
            db.session.commit()
            flash("تم حفظ المنتج.", "success")
            return redirect(url_for("admin.products"))
    return render_template("admin/product_form.html", form=form, product=product)


@bp.post("/products/<int:product_id>/delete")
@admin_required
def product_delete(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    if Order.query.join(Order.items).filter_by(product_id=product.id).first():
        product.is_active = False
        flash("المنتج مرتبط بطلبات سابقة، لذا تم إخفاؤه بدلاً من حذفه.", "info")
    else:
        db.session.delete(product)
        flash("تم حذف المنتج.", "success")
    db.session.commit()
    return redirect(url_for("admin.products"))


@bp.get("/categories")
@admin_required
def categories():
    return render_template("admin/categories.html", categories=Category.query.order_by(Category.name).all())


@bp.route("/categories/new", methods=["GET", "POST"])
@bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@admin_required
def category_form(category_id=None):
    category = db.session.get(Category, category_id) if category_id else Category()
    if category_id and not category:
        abort(404)
    form = CategoryForm(obj=category)
    if form.validate_on_submit():
        category.name = form.name.data.strip()
        category.slug = slugify(category.name)
        slug_match = Category.query.filter(Category.slug == category.slug, Category.id != (category.id or 0)).first()
        if slug_match:
            category.slug = f"{category.slug}-{uuid4().hex[:8]}"
        category.description = form.description.data or ""
        category.is_active = form.is_active.data
        if form.image.data:
            try:
                category.image = save_image(form.image.data)
            except ValueError as exc:
                flash(str(exc), "error")
                return render_template("admin/category_form.html", form=form, category=category)
        db.session.add(category)
        db.session.commit()
        flash("تم حفظ التصنيف.", "success")
        return redirect(url_for("admin.categories"))
    return render_template("admin/category_form.html", form=form, category=category)


@bp.post("/categories/<int:category_id>/delete")
@admin_required
def category_delete(category_id):
    category = db.session.get(Category, category_id) or abort(404)
    category.is_active = False
    db.session.commit()
    flash("تم إخفاء التصنيف للحفاظ على روابط المنتجات.", "success")
    return redirect(url_for("admin.categories"))


@bp.get("/orders")
@admin_required
def orders():
    query = Order.query
    status = request.args.get("status", "")
    search = request.args.get("q", "").strip()
    if status in ORDER_STATUSES:
        query = query.filter_by(status=status)
    if search:
        like = f"%{search}%"
        query = query.filter((Order.order_number.ilike(like)) | (Order.customer_name.ilike(like)) | (Order.phone.ilike(like)))
    return render_template("admin/orders.html", orders=query.order_by(Order.created_at.desc()).all(),
                           status_labels=STATUS_LABELS, order_statuses=ORDER_STATUSES, selected_status=status, search=search)


@bp.route("/orders/<int:order_id>", methods=["GET", "POST"])
@admin_required
def order_detail(order_id):
    order = db.session.get(Order, order_id) or abort(404)
    if request.method == "POST":
        status = request.form.get("status")
        if status not in ORDER_STATUSES:
            abort(400)
        # Delivered/cancelled orders cannot be reopened automatically after inventory has changed.
        if order.status in {"delivered", "cancelled"} and status != order.status:
            flash("لا يمكن إعادة فتح طلب مكتمل أو ملغي من لوحة الإدارة.", "error")
        else:
            if status == "cancelled" and order.status != "cancelled":
                for item in order.items:
                    if item.product_id:
                        db.session.execute(
                            update(Product).where(Product.id == item.product_id)
                            .values(stock=Product.stock + item.quantity)
                        )
            order.status = status
            db.session.commit()
            flash("تم تحديث حالة الطلب.", "success")
        return redirect(url_for("admin.order_detail", order_id=order.id))
    return render_template("admin/order_detail.html", order=order, status_labels=STATUS_LABELS, order_statuses=ORDER_STATUSES)


@bp.get("/shipping")
@admin_required
def shipping():
    rates = ShippingRate.query.order_by(ShippingRate.governorate, ShippingRate.city, ShippingRate.area).all()
    return render_template("admin/shipping.html", rates=rates, governorates=EGYPT_GOVERNORATES)


@bp.post("/shipping/save")
@admin_required
def shipping_save():
    gov = request.form.get("governorate", "")
    city = request.form.get("city", "").strip()
    area = request.form.get("area", "").strip()
    raw_fee = request.form.get("fee", "")
    if gov not in EGYPT_GOVERNORATES:
        abort(400)
    try:
        fee = Decimal(raw_fee)
        if fee < 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        flash("أدخل سعر توصيل صحيحاً.", "error")
        return redirect(url_for("admin.shipping"))
    rate = ShippingRate.query.filter_by(governorate=gov, city=city, area=area).first()
    if not rate:
        rate = ShippingRate(governorate=gov, city=city, area=area)
    rate.fee = fee
    rate.is_active = True
    db.session.add(rate)
    db.session.commit()
    flash("تم حفظ سعر التوصيل.", "success")
    return redirect(url_for("admin.shipping"))


@bp.post("/shipping/<int:rate_id>/toggle")
@admin_required
def shipping_toggle(rate_id):
    rate = db.session.get(ShippingRate, rate_id) or abort(404)
    rate.is_active = not rate.is_active
    db.session.commit()
    return redirect(url_for("admin.shipping"))


@bp.get("/customers.csv")
@admin_required
def customers_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "email", "phone", "created_at", "orders"])
    for customer in Customer.query.order_by(Customer.created_at.desc()).all():
        writer.writerow([customer.id, customer.full_name, customer.email, customer.phone,
                         customer.created_at.isoformat(), len(customer.orders)])
    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=rijoya-customers.csv"
    return response
