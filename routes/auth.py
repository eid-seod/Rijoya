import sqlite3
from functools import wraps

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint("auth", __name__, url_prefix="", template_folder="../templates/auth")


def _app_helpers():
    """Load app helpers lazily so importing routes.auth cannot import app recursively."""
    from app import (
        create_session,
        destroy_session,
        find_user,
        get_db,
        identity_from_session,
        login_required,
        role_id,
        utc_now,
    )
    return locals()


def _login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        return _app_helpers()["login_required"](view)(*args, **kwargs)
    return wrapped


@auth_bp.route("/auth", methods=["GET", "POST"])
def login():
    helpers = _app_helpers()
    if request.method == "POST":
        action = request.form.get("action")
        username = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password or (action == "register" and not username):
            flash("Please complete all required fields.", "error")
            return render_template("auth/auth.html")
        db = helpers["get_db"]()
        if action == "register":
            try:
                db.execute("INSERT INTO users (username, email, password_hash, role_id, status, created_at) VALUES (?, ?, ?, ?, 'active', ?)", (username, email, generate_password_hash(password), helpers["role_id"]("customer"), helpers["utc_now"]()))
                db.commit()
                helpers["create_session"](helpers["find_user"](email))
                flash("Account created. Welcome to Rijoya!", "success")
                return redirect(url_for("shop.customer_dashboard"))
            except sqlite3.IntegrityError:
                flash("That email or username is already registered.", "error")
        else:
            user = helpers["find_user"](email)
            if user and user["status"] == "active" and check_password_hash(user["password_hash"], password):
                helpers["create_session"](user)
                flash("Welcome back!", "success")
                identity = helpers["identity_from_session"]()
                if user["role_name"] in {"admin", "super_admin"}:
                    return redirect(url_for("admin.dashboard"))
                if identity and identity.get("vendor") and identity["vendor"]["status"] == "approved":
                    return redirect(url_for("vendor.dashboard"))
                return redirect(url_for("shop.customer_dashboard"))
            flash("Email or password is incorrect, or this account is suspended.", "error")
    return render_template("auth/auth.html")


@auth_bp.post("/api/auth/login")
def api_login():
    helpers = _app_helpers()
    data = request.get_json(silent=True) or request.form
    user = helpers["find_user"](data.get("email", "").strip().lower())
    if not user or user["status"] != "active" or not check_password_hash(user["password_hash"], data.get("password", "")):
        return jsonify(error="Invalid credentials"), 401
    helpers["create_session"](user)
    return jsonify(success=True, user_id=user["id"], role=user["role_name"], session_id=session["session_id"])


@auth_bp.get("/api/auth/me")
@_login_required
def api_me():
    identity = _app_helpers()["identity_from_session"]()
    return jsonify(user={"id": identity["user"]["id"], "username": identity["user"]["username"], "email": identity["user"]["email"]}, role=identity["role"], permissions=sorted(identity["permissions"]), last_login=identity["session"]["login_time"])


@auth_bp.get("/logout")
def logout():
    _app_helpers()["destroy_session"]()
    flash("You have been logged out.", "success")
    return redirect(url_for("shop.home"))


@auth_bp.context_processor
def auth_template_context():
    return {"auth_area": True}
