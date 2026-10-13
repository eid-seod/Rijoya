from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app
from extensions import db, login_manager
from models.models import Admin, Customer


def reset_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="rijoya-password-reset")


def make_reset_token(email):
    return reset_serializer().dumps(email, salt="email")


def read_reset_token(token, max_age=3600):
    try:
        return reset_serializer().loads(token, salt="email", max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


@login_manager.user_loader
def load_user(user_id):
    if not user_id or ":" not in user_id:
        return None
    kind, raw_id = user_id.split(":", 1)
    if not raw_id.isdigit():
        return None
    if kind == "admin":
        return db.session.get(Admin, int(raw_id))
    if kind == "customer":
        return db.session.get(Customer, int(raw_id))
    return None
