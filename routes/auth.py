import sqlite3
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from app import create_session, current_user, find_user, get_db, identity_from_session, role_id, destroy_session, utc_now, login_required

auth_bp = Blueprint("auth", __name__, url_prefix="", template_folder="../templates/auth")

@auth_bp.route("/auth", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        action = request.form.get("action")
        username = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password or (action == "register" and not username):
            flash("Please complete all required fields.", "error")
            return render_template("auth/auth.html")
        db = get_db()
        if action == "register":
            try:
                db.execute("INSERT INTO users (username, email, password_hash, role_id, status, created_at) VALUES (?, ?, ?, ?, 'active', ?)", (username, email, generate_password_hash(password), role_id("customer"), utc_now()))
                db.commit()
                create_session(find_user(email))
                flash("Account created. Welcome to Rijoya!", "success")
                return redirect(url_for("shop.customer_dashboard"))
            except sqlite3.IntegrityError:
                flash("That email or username is already registered.", "error")
        else:
            user = find_user(email)
            if user and user["status"] == "active" and check_password_hash(user["password_hash"], password):
                create_session(user)
                flash("Welcome back!", "success")
                if user["role_name"] in {"admin", "super_admin"}:
                    return redirect(url_for("admin.dashboard"))
                if identity_from_session().get("vendor") and identity_from_session()["vendor"]["status"] == "approved":
                    return redirect(url_for("vendor.dashboard"))
                return redirect(url_for("shop.customer_dashboard"))
            flash("Email or password is incorrect, or this account is suspended.", "error")
    return render_template("auth/auth.html")

@auth_bp.post("/api/auth/login")
def api_login():
    data = request.get_json(silent=True) or request.form
    user = find_user(data.get("email", "").strip().lower())
    if not user or user["status"] != "active" or not check_password_hash(user["password_hash"], data.get("password", "")):
        return jsonify(error="Invalid credentials"), 401
    create_session(user)
    return jsonify(success=True, user_id=user["id"], role=user["role_name"], session_id=session["session_id"])

@auth_bp.get("/api/auth/me")
@login_required
def api_me():
    identity = identity_from_session()
    return jsonify(user={"id": identity["user"]["id"], "username": identity["user"]["username"], "email": identity["user"]["email"]}, role=identity["role"], permissions=sorted(identity["permissions"]), last_login=identity["session"]["login_time"])

@auth_bp.get("/logout")
def logout():
    destroy_session()
    flash("You have been logged out.", "success")
    return redirect(url_for("shop.home"))

@auth_bp.context_processor
def auth_template_context():
    return {"auth_area": True}
