import secrets
from urllib.parse import urlsplit
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user
from extensions import db
from forms import LoginForm, RegisterForm
from models.models import Admin, CartItem, Customer
from utils.auth import make_reset_token, read_reset_token

bp = Blueprint("auth", __name__)


def _safe_next_url(target):
    if not target:
        return None
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/") or target.startswith("//"):
        return None
    return target


def _merge_guest_cart(customer):
    guest = session.pop("cart_items", {})
    for raw_id, raw_qty in guest.items():
        if not str(raw_id).isdigit():
            continue
        try:
            product_id, quantity = int(raw_id), max(1, int(raw_qty))
        except (TypeError, ValueError):
            continue
        item = CartItem.query.filter_by(customer_id=customer.id, product_id=product_id).first()
        available = item.product.stock if item and item.product else None
        if item:
            if not available:
                db.session.delete(item)
            else:
                item.quantity = min(item.quantity + quantity, available)
        else:
            from models.models import Product
            product = db.session.get(Product, product_id)
            if product and product.is_active and product.stock > 0:
                db.session.add(CartItem(customer_id=customer.id, product_id=product_id, quantity=min(quantity, product.stock)))
    db.session.commit()


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("shop.home"))
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = Customer.query.filter_by(email=email).first()
        admin = Admin.query.filter_by(email=email).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            _merge_guest_cart(user)
            return redirect(_safe_next_url(request.args.get("next")) or url_for("shop.home"))
        if admin and admin.check_password(form.password.data):
            login_user(admin, remember=form.remember.data)
            return redirect(url_for("admin.dashboard"))
        flash("البريد الإلكتروني أو كلمة المرور غير صحيحة.", "error")
    return render_template("auth/login.html", form=form)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("shop.home"))
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if Customer.query.filter_by(email=email).first() or Admin.query.filter_by(email=email).first():
            flash("هذا البريد الإلكتروني مسجل بالفعل.", "error")
        else:
            customer = Customer(full_name=form.full_name.data.strip(), email=email, phone=form.phone.data.strip())
            customer.set_password(form.password.data)
            db.session.add(customer)
            db.session.commit()
            login_user(customer)
            _merge_guest_cart(customer)
            flash("أهلاً بك في ريجويا! تم إنشاء حسابك.", "success")
            return redirect(url_for("shop.home"))
    return render_template("auth/register.html", form=form)


@bp.post("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
    return redirect(url_for("shop.home"))


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        customer = Customer.query.filter_by(email=email).first()
        if customer:
            token = make_reset_token(customer.email)
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            current_app.logger.info("Password reset link for %s: %s", customer.email, reset_url)
            if current_app.debug or current_app.testing:
                flash(f"رابط إعادة التعيين للتطوير: {reset_url}", "info")
        flash("إذا كان البريد مسجلاً، ستصل تعليمات إعادة التعيين قريباً.", "success")
        return redirect(url_for("auth.forgot_password"))
    return render_template("auth/forgot_password.html")


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    email = read_reset_token(token)
    customer = Customer.query.filter_by(email=email).first() if email else None
    if not customer:
        flash("رابط إعادة التعيين غير صالح أو منتهي الصلاحية.", "error")
        return redirect(url_for("auth.forgot_password"))
    if request.method == "POST":
        password = request.form.get("password", "")
        confirmation = request.form.get("confirm", "")
        if len(password) < 8:
            flash("يجب أن تتكون كلمة المرور من 8 أحرف على الأقل.", "error")
        elif password != confirmation:
            flash("كلمتا المرور غير متطابقتين.", "error")
        else:
            customer.set_password(password)
            db.session.commit()
            flash("تم تحديث كلمة المرور. يمكنك تسجيل الدخول الآن.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html")
