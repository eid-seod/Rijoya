from pathlib import Path
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, flash, g, jsonify, redirect, request, session, url_for
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "rijoya.db"
SCHEMA = BASE_DIR / "schema.sql"
SESSION_TIMEOUT_MINUTES = 30

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("FLASK_SECRET_KEY", "change-this-secret-key"),
    DATABASE=DATABASE,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=SESSION_TIMEOUT_MINUTES),
)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db():
    if "db" not in g:
        if not Path(app.config["DATABASE"]).exists() or database_needs_initialization():
            init_db()
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def database_needs_initialization():
    if not Path(app.config["DATABASE"]).exists():
        return True
    db = sqlite3.connect(app.config["DATABASE"])
    required_tables = {"users", "sessions", "order_items", "addresses", "vendors"}
    existing = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
    if not required_tables.issubset(existing):
        db.close()
        return True
    columns = {row[1] for row in db.execute("PRAGMA table_info(vendors)").fetchall()}
    db.close()
    return "user_id" not in columns or "store_name" not in columns


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(app.config["DATABASE"])
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA.read_text())
    for email, password in {
        "demo@rijoya.local": "demo-password",
        "admin@rijoya.local": "admin123",
        "ops@rijoya.local": "admin123",
        "vendor@rijoya.local": "vendor123",
    }.items():
        db.execute("UPDATE users SET password_hash = ?, status = 'active' WHERE email = ?", (generate_password_hash(password), email))
    db.commit()
    db.close()


def role_id(name):
    row = get_db().execute("SELECT id FROM roles WHERE name = ?", (name,)).fetchone()
    return row["id"]


def find_user(email):
    return get_db().execute(
        "SELECT users.*, roles.name AS role_name FROM users JOIN roles ON roles.id = users.role_id WHERE users.email = ?",
        (email,),
    ).fetchone()


def permissions_for(user):
    db = get_db()
    permissions = {row["name"] for row in db.execute("SELECT permissions.name FROM permissions JOIN role_permissions ON role_permissions.permission_id = permissions.id WHERE role_permissions.role_id = ?", (user["role_id"],)).fetchall()}
    permissions.update(row["name"] for row in db.execute("SELECT permissions.name FROM permissions JOIN user_permissions ON user_permissions.permission_id = permissions.id WHERE user_permissions.user_id = ?", (user["id"],)).fetchall())
    return {"*"} if user["role_name"] == "super_admin" else permissions


def identity_from_session():
    if hasattr(g, "identity"):
        return g.identity
    user_id, session_id = session.get("user_id"), session.get("session_id")
    if not user_id or not session_id:
        g.identity = None
        return None
    db = get_db()
    active = db.execute("SELECT sessions.*, users.status FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.id = ? AND sessions.user_id = ?", (session_id, user_id)).fetchone()
    if not active or active["status"] != "active":
        session.clear()
        g.identity = None
        return None
    try:
        last_activity = datetime.fromisoformat(active["last_activity"])
    except ValueError:
        last_activity = datetime.now(timezone.utc) - timedelta(minutes=SESSION_TIMEOUT_MINUTES + 1)
    if datetime.now(timezone.utc) - last_activity > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
        db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        db.commit()
        session.clear()
        g.identity = None
        return None
    user = db.execute("SELECT users.*, roles.name AS role_name FROM users JOIN roles ON roles.id = users.role_id WHERE users.id = ? AND users.status = 'active'", (user_id,)).fetchone()
    if not user:
        session.clear()
        g.identity = None
        return None
    db.execute("UPDATE sessions SET last_activity = ? WHERE id = ?", (utc_now(), session_id))
    db.commit()
    vendor = db.execute("SELECT * FROM vendors WHERE user_id = ?", (user_id,)).fetchone()
    g.identity = {"user": user, "role": user["role_name"], "permissions": permissions_for(user), "vendor": vendor, "session": active}
    return g.identity


def current_user():
    identity = identity_from_session()
    return identity["user"] if identity else None


def is_api_request():
    return request.path.startswith("/api/") or request.is_json


def unauthorized():
    if is_api_request():
        return jsonify(error="Authentication required"), 401
    flash("Please log in first.", "error")
    return redirect(url_for("auth.login", next=request.path))


def forbidden(message="You do not have permission to perform this action."):
    if is_api_request():
        return jsonify(error=message), 403
    flash(message, "error")
    return redirect(request.referrer or url_for("shop.home"))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not identity_from_session():
            return unauthorized()
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            identity = identity_from_session()
            if not identity:
                return unauthorized()
            if identity["role"] == "super_admin" or identity["role"] in roles:
                return view(*args, **kwargs)
            return forbidden("Your role cannot access this area.")
        return wrapped
    return decorator


def admin_required(view):
    return role_required("admin", "super_admin")(view)


def super_admin_required(view):
    return role_required("super_admin")(view)


def vendor_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        identity = identity_from_session()
        if not identity:
            return unauthorized()
        vendor = identity.get("vendor")
        if not vendor or vendor["status"] != "approved":
            flash("Your approved vendor account is required for the vendor portal.", "error")
            return redirect(url_for("vendor.apply"))
        return view(*args, **kwargs)
    return wrapped


def permission_required(permission):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            identity = identity_from_session()
            if not identity:
                return unauthorized()
            if identity["role"] == "super_admin" or permission in identity["permissions"]:
                return view(*args, **kwargs)
            return forbidden(f"The '{permission}' permission is required.")
        return wrapped
    return decorator


def create_session(user):
    db = get_db()
    session_id = secrets.token_urlsafe(32)
    now = utc_now()
    db.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
    db.execute("INSERT INTO sessions (id, user_id, login_time, last_activity, ip_address) VALUES (?, ?, ?, ?, ?)", (session_id, user["id"], now, now, request.remote_addr or "unknown"))
    db.commit()
    session.clear()
    session.permanent = True
    session.update(user_id=user["id"], role=user["role_name"], session_id=session_id)


def destroy_session():
    session_id = session.get("session_id")
    if session_id:
        get_db().execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        get_db().commit()
    session.clear()


def get_cart_items():
    ids = session.get("cart", [])
    if not ids:
        return []
    marks = ",".join("?" for _ in ids)
    return get_db().execute(f"SELECT products.*, vendors.store_name AS vendor_name FROM products JOIN vendors ON vendors.id = products.vendor_id WHERE products.id IN ({marks}) AND products.status = 'approved' AND vendors.status = 'approved'", ids).fetchall()


@app.context_processor
def shared_template_data():
    identity = identity_from_session()
    return {"cart_count": len(session.get("cart", [])), "current_user": identity["user"]["username"] if identity else None, "current_role": identity["role"] if identity else None, "is_admin": bool(identity and identity["role"] in {"admin", "super_admin"}), "is_super_admin": bool(identity and identity["role"] == "super_admin"), "is_vendor": bool(identity and identity.get("vendor") and identity["vendor"]["status"] == "approved"), "permissions": sorted(identity["permissions"]) if identity else []}


from routes.auth import auth_bp
from routes.shop import shop_bp
from routes.vendor import vendor_bp
from routes.admin import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(shop_bp)
app.register_blueprint(vendor_bp)
app.register_blueprint(admin_bp)


@app.cli.command("init-db")
def init_db_command():
    init_db()
    print("Initialized the Rijoya SQLite database.")


if __name__ == "__main__":
    if not DATABASE.exists():
        init_db()
    app.run(debug=True)
