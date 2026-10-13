from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from extensions import db
from forms import RegisterForm
from models.models import Order

bp = Blueprint("account", __name__, url_prefix="/account")


def customer_required(view):
    from functools import wraps
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))
        return view(*args, **kwargs)
    return wrapped


@bp.get("/")
@customer_required
def dashboard():
    orders = Order.query.filter_by(customer_id=current_user.id).order_by(Order.created_at.desc()).limit(10).all()
    return render_template("account/dashboard.html", orders=orders)


@bp.route("/profile", methods=["GET", "POST"])
@customer_required
def profile():
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        if len(name) < 2 or len(phone) < 8:
            flash("يرجى إدخال الاسم ورقم هاتف صحيح.", "error")
        else:
            current_user.full_name = name[:120]
            current_user.phone = phone[:30]
            db.session.commit()
            flash("تم تحديث بياناتك.", "success")
            return redirect(url_for("account.profile"))
    return render_template("account/profile.html")


@bp.get("/orders/<int:order_id>")
@customer_required
def order_detail(order_id):
    order = Order.query.filter_by(id=order_id, customer_id=current_user.id).first_or_404()
    return render_template("account/order_detail.html", order=order)
