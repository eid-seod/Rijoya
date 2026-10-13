import click
from flask import Flask, jsonify
from sqlalchemy import event
from config import Config
from extensions import csrf, db, login_manager
from utils.seed import seed_database


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": {"check_same_thread": False}}
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from routes.auth import bp as auth_bp
    from routes.shop import bp as shop_bp
    from routes.account import bp as account_bp
    from routes.admin import bp as admin_bp
    from routes.api import bp as api_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    def enable_sqlite_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    with app.app_context():
        engine = db.engine
        if engine.dialect.name == "sqlite":
            event.listen(engine, "connect", enable_sqlite_foreign_keys)

    @app.get("/health")
    def health():
        return jsonify(status="ok", service="rijoya")

    @app.context_processor
    def inject_store_globals():
        from models.models import Category
        from flask_login import current_user
        cart_count = 0
        if current_user.is_authenticated and not current_user.is_admin:
            from models.models import CartItem
            cart_count = sum(row.quantity for row in CartItem.query.filter_by(customer_id=current_user.id).all())
        else:
            from flask import session
            cart_count = sum(int(q) for q in session.get("cart_items", {}).values())
        return {"store_categories": Category.query.filter_by(is_active=True).order_by(Category.name).all(), "cart_count": cart_count}

    @app.cli.command("seed")
    def seed_command():
        """Create the schema and seed the single admin, demo catalog and shipping rates."""
        seed_database(app)
        click.echo("Rijoya database is ready. Set ADMIN_EMAIL and ADMIN_PASSWORD before production use.")

    @app.cli.command("routes-list")
    def routes_list():
        for rule in sorted(app.url_map.iter_rules(), key=lambda item: item.rule):
            click.echo(f"{rule.rule:35} {','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'})):18} {rule.endpoint}")

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response

    seed_database(app)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=False)
