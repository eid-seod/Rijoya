# Rijoya Flask MVP

A beginner-friendly multi-vendor marketplace built with **HTML, CSS, JavaScript, Python, Flask, and SQLite**.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

The first run creates `rijoya.db` from `schema.sql` and adds a few sample vendors and products. To reset the database, delete `rijoya.db` and run the app again.

Demo login:

- Email: `demo@rijoya.local`
- Password: `demo-password`

## Main pages

- `/` — product home page
- `/auth` — login and registration
- `/vendor/register` — vendor registration
- `/products` — product list and vendor upload form
- `/cart` — add/remove products
- `/checkout` — confirm an order
- `/logout` — clear the current session

## Database

The SQL schema is in `schema.sql` and creates:

- `users`
- `vendors`
- `products`
- `orders`

Orders are stored as one row per product in the cart to keep the MVP schema simple.

## Important MVP notes

This is intentionally a learning-friendly MVP. It uses SQLite, Flask sessions, a basic hashed password for newly registered users, and a simple confirmation checkout. It does not process real payments, calculate shipping, send email, or provide production-grade authorization yet.
