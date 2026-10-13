# Rijoya Egypt E-Commerce

Arabic-first RTL storefront and admin starter for an Egypt-focused store. Built with Flask 3, SQLAlchemy, SQLite, Jinja, Flask-Login, Flask-WTF, and WTForms. The default run target is `0.0.0.0:3000`.

## Included

- Server-rendered Arabic RTL storefront, search, category browsing, product pages, responsive editorial design, and safe image placeholders.
- Guest session cart and registered-customer cart, cart merging after login, stock-aware checkout, and inventory decrement inside the order transaction.
- Guest and registered checkout; a phone number is required and COD is the only permitted payment method.
- Order number format `ORD-YYYYMMDD-000001`; immutable item-name/SKU/price snapshots survive product edits.
- Admin cancellation of an active order restores its reserved stock once; delivered and cancelled orders cannot be reopened through the dashboard.
- Customer registration, sign-in, profile, order history, and signed, expiring password-reset tokens (email delivery is intentionally not configured).
- Single seeded super-admin, separate admin UI, product/category CRUD, order search and status transitions, customer CSV export, and governorate/city/area shipping-rate management.
- Public JSON catalog and session-aware cart endpoints under `/api/`, plus admin-protected JSON product/category CRUD at `/api/admin/` (session login and CSRF required for writes).
- Uploads are stored under `static/uploads/` using generated safe filenames; only allowed image extensions and a 5 MiB request cap are accepted. Replace the storage adapter later if moving to object storage.

## Local setup

Python 3.11+ is recommended.

```bash
cd Rijoya
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

The service listens on `http://localhost:3000`. Database schema and idempotent demo data are created when the app starts. The database file is `database.db`.

For a production-style WSGI process, install requirements and run `gunicorn --bind 0.0.0.0:3000 --workers 1 --threads 4 wsgi:application` (also declared in `Procfile`). The single worker is intentional for the initial SQLite deployment.

To initialize or re-apply seed data explicitly:

```bash
flask --app app seed
```

`flask --app app routes-list` lists the route map. `GET /health` is the lightweight health check.

## Development admin

Admin sign-in: `/admin/login`. Set `ADMIN_EMAIL` and a unique `ADMIN_PASSWORD` in `.env` before the first run. If the password is blank, the first app start generates a high-entropy one-time password and logs it once; capture it from the startup output. Setting a new `ADMIN_PASSWORD` later resets the configured single admin's hash on the next startup. The app has no admin self-registration or multi-admin UI.

## Configuration

Copy `.env.example` and set a stable, high-entropy `SECRET_KEY`, `ADMIN_EMAIL`, and unique `ADMIN_PASSWORD` for a real deployment. `COOKIE_SECURE=1` should be set behind HTTPS. If `SECRET_KEY` is blank, a random process secret is used (sessions will not survive a restart). `DATABASE_URL` may override SQLite if an external SQLAlchemy-compatible database is introduced. Do not commit `.env`, `database.db`, or customer uploads.

### Seed data and shipping

The starter catalog has three Arabic categories and sample products. On a genuinely empty database, the first seed also adds a fictional sample customer and one completed sample order for admin-dashboard review; do not treat either as a real customer/order. Remove those test records directly from the database before taking live orders. It creates a default governorate-level rate for all 27 Egyptian governorates (65 EGP for Cairo/Giza, 85 EGP elsewhere); edit these example amounts in **Admin → أسعار التوصيل**. A matching area rate wins over a city rate, which wins over the governorate default.

### Password reset

The reset flow creates a signed token that expires after one hour and logs the generated link. A production email provider is intentionally left out; connect one before relying on password reset outside development. Responses do not disclose whether an email exists.

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Production checklist

- Set stable secrets and an admin password; use HTTPS and `COOKIE_SECURE=1`.
- Change example shipping fees and demo products/categories.
- Configure email delivery and operational support/contact details.
- Use a production WSGI server (for example Gunicorn) and a managed database for multi-worker deployments; SQLite is intended for the initial single-service starter.
- Back up the database and move media to durable object storage if needed.
- Add policy pages, final brand imagery, and a deployment-specific privacy/retention review before launch.

## Project map

```text
app.py                 app factory, CLI, health endpoint
config.py              environment-based settings
extensions.py          SQLAlchemy, login and CSRF extensions
forms.py               WTForms validation
models/models.py        commerce schema and relationships
routes/                 auth, storefront, account, admin and JSON routes
utils/                  seed, image, shipping and reset-token helpers
templates/              Arabic RTL Jinja views
static/css/app.css      Nile Modernism design system
static/js/app.js        menu and fetch helpers
schema.sql              normalized reference schema
```
