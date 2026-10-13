from decimal import Decimal, InvalidOperation
from functools import wraps
from uuid import uuid4
from flask import Blueprint, abort, jsonify, request
from flask_login import current_user
from extensions import db
from models.models import Category, Product
from routes.shop import cart_rows, change_cart
from utils.helpers import slugify

bp = Blueprint("api", __name__, url_prefix="/api")


def product_json(product):
    return {"id": product.id, "name": product.name, "slug": product.slug,
            "description": product.description, "price": str(product.price),
            "compare_at_price": str(product.compare_at_price) if product.compare_at_price is not None else None,
            "stock": product.stock, "sku": product.sku,
            "category": product.category.name if product.category else None,
            "category_id": product.category_id, "image": product.image or None,
            "is_active": product.is_active, "is_featured": product.is_featured,
            "available": product.available}


def category_json(category):
    return {"id": category.id, "name": category.name, "slug": category.slug,
            "description": category.description, "image": category.image or None,
            "is_active": category.is_active}


def api_admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify(error="authentication_required"), 401
        if not current_user.is_admin:
            return jsonify(error="admin_required"), 403
        return view(*args, **kwargs)
    return wrapped


def _unique_slug(model, name, current_id=None):
    slug = slugify(name)
    query = model.query.filter_by(slug=slug)
    if current_id:
        query = query.filter(model.id != current_id)
    if query.first():
        slug = f"{slug}-{uuid4().hex[:8]}"
    return slug


def _decimal(value, label):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0:
            raise InvalidOperation
        return amount
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{label} must be a non-negative number")


def _integer(value, label, minimum=0):
    try:
        number = int(value)
        if number < minimum:
            raise ValueError
        return number
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be an integer >= {minimum}")


@bp.get("/products")
def products():
    query = Product.query.filter_by(is_active=True)
    category = request.args.get("category")
    if category:
        query = query.join(Category).filter(Category.slug == category, Category.is_active.is_(True))
    return jsonify(items=[product_json(item) for item in query.order_by(Product.name).all()])


@bp.get("/products/<slug>")
def product_detail(slug):
    product = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
    return jsonify(item=product_json(product))


@bp.get("/categories")
def categories():
    return jsonify(items=[category_json(item) for item in Category.query.filter_by(is_active=True).order_by(Category.name).all()])


@bp.get("/categories/<slug>")
def category_detail(slug):
    category = Category.query.filter_by(slug=slug, is_active=True).first_or_404()
    products = Product.query.filter_by(category_id=category.id, is_active=True).order_by(Product.name).all()
    return jsonify(item=category_json(category), products=[product_json(product) for product in products])


@bp.route("/admin/products", methods=["GET", "POST"])
@api_admin_required
def admin_products():
    if request.method == "GET":
        return jsonify(items=[product_json(item) for item in Product.query.order_by(Product.id).all()])
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="json_object_required"), 400
    try:
        name = str(payload.get("name", "")).strip()
        sku = str(payload.get("sku", "")).strip()
        if not name or len(name) > 160 or not sku or len(sku) > 60:
            raise ValueError("name and sku are required and must fit their field limits")
        if Product.query.filter_by(sku=sku).first():
            raise ValueError("sku_already_exists")
        category_id = _integer(payload["category_id"], "category_id", 1) if payload.get("category_id") else None
        if category_id and not db.session.get(Category, category_id):
            raise ValueError("category_not_found")
        price = _decimal(payload.get("price"), "price")
        stock = _integer(payload.get("stock", 0), "stock")
        compare = _decimal(payload["compare_at_price"], "compare_at_price") if payload.get("compare_at_price") is not None else None
        product = Product(name=name, slug=_unique_slug(Product, name), sku=sku,
            category_id=category_id, description=str(payload.get("description", ""))[:5000],
            price=price, compare_at_price=compare, stock=stock,
            is_active=payload.get("is_active", True) is True,
            is_featured=payload.get("is_featured", False) is True)
        db.session.add(product)
        db.session.commit()
        return jsonify(item=product_json(product)), 201
    except ValueError as exc:
        db.session.rollback()
        return jsonify(error=str(exc)), 400


@bp.route("/admin/products/<int:product_id>", methods=["GET", "PATCH", "PUT", "DELETE"])
@api_admin_required
def admin_product_detail(product_id):
    product = db.session.get(Product, product_id) or abort(404)
    if request.method == "GET":
        return jsonify(item=product_json(product))
    if request.method == "DELETE":
        product.is_active = False
        db.session.commit()
        return jsonify(item=product_json(product), message="product_deactivated")
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="json_object_required"), 400
    try:
        if "name" in payload:
            name = str(payload["name"]).strip()
            if not name or len(name) > 160:
                raise ValueError("invalid_name")
            product.name = name
            product.slug = _unique_slug(Product, name, product.id)
        if "sku" in payload:
            sku = str(payload["sku"]).strip()
            if not sku or len(sku) > 60 or Product.query.filter(Product.sku == sku, Product.id != product.id).first():
                raise ValueError("invalid_or_duplicate_sku")
            product.sku = sku
        if "category_id" in payload:
            product.category_id = _integer(payload["category_id"], "category_id", 1) if payload["category_id"] is not None else None
            if product.category_id and not db.session.get(Category, product.category_id):
                raise ValueError("category_not_found")
        if "price" in payload:
            product.price = _decimal(payload["price"], "price")
        if "compare_at_price" in payload:
            product.compare_at_price = _decimal(payload["compare_at_price"], "compare_at_price") if payload["compare_at_price"] is not None else None
        if "stock" in payload:
            product.stock = _integer(payload["stock"], "stock")
        if "description" in payload:
            product.description = str(payload["description"])[:5000]
        for field in ("is_active", "is_featured"):
            if field in payload:
                if not isinstance(payload[field], bool):
                    raise ValueError(f"{field} must be boolean")
                setattr(product, field, payload[field])
        db.session.commit()
        return jsonify(item=product_json(product))
    except ValueError as exc:
        db.session.rollback()
        return jsonify(error=str(exc)), 400


@bp.route("/admin/categories", methods=["GET", "POST"])
@api_admin_required
def admin_categories():
    if request.method == "GET":
        return jsonify(items=[category_json(item) for item in Category.query.order_by(Category.id).all()])
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="json_object_required"), 400
    name = str(payload.get("name", "")).strip()
    if not name or len(name) > 100:
        return jsonify(error="valid_name_required"), 400
    category = Category(name=name, slug=_unique_slug(Category, name),
        description=str(payload.get("description", ""))[:500],
        is_active=payload.get("is_active", True) is True)
    db.session.add(category)
    db.session.commit()
    return jsonify(item=category_json(category)), 201


@bp.route("/admin/categories/<int:category_id>", methods=["GET", "PATCH", "PUT", "DELETE"])
@api_admin_required
def admin_category_detail(category_id):
    category = db.session.get(Category, category_id) or abort(404)
    if request.method == "GET":
        return jsonify(item=category_json(category))
    if request.method == "DELETE":
        category.is_active = False
        db.session.commit()
        return jsonify(item=category_json(category), message="category_deactivated")
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="json_object_required"), 400
    if "name" in payload:
        name = str(payload["name"]).strip()
        if not name or len(name) > 100:
            return jsonify(error="invalid_name"), 400
        category.name = name
        category.slug = _unique_slug(Category, name, category.id)
    if "description" in payload:
        category.description = str(payload["description"])[:500]
    if "is_active" in payload:
        if not isinstance(payload["is_active"], bool):
            return jsonify(error="is_active_must_be_boolean"), 400
        category.is_active = payload["is_active"]
    db.session.commit()
    return jsonify(item=category_json(category))


@bp.get("/cart")
def get_cart():
    rows = cart_rows()
    items = [{"product_id": row["product"].id, "name": row["product"].name,
              "quantity": row["quantity"], "unit_price": str(row["product"].price),
              "line_total": str(row["product"].price * row["quantity"])} for row in rows]
    subtotal = sum((row["product"].price * row["quantity"] for row in rows), start=Decimal("0.00"))
    return jsonify(items=items, subtotal=str(subtotal), count=sum(i["quantity"] for i in items))


@bp.post("/cart")
def update_cart():
    payload = request.get_json(silent=True) or {}
    product_id, quantity = payload.get("product_id"), payload.get("quantity")
    try:
        product_id, quantity = int(product_id), int(quantity)
    except (TypeError, ValueError):
        return jsonify(error="product_id and quantity must be integers"), 400
    ok, message = change_cart(product_id, quantity)
    if not ok:
        return jsonify(error=message), 404
    rows = cart_rows()
    subtotal = sum((row["product"].price * row["quantity"] for row in rows), start=Decimal("0.00"))
    return jsonify(message=message, count=sum(row["quantity"] for row in rows), subtotal=str(subtotal))
