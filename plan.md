# Rijoya Egypt E-Commerce — Implementation Notes

## Scope delivered

A single Flask service on port 3000 with an app factory, SQLite/SQLAlchemy data layer, server-rendered Jinja storefront, a separate admin visual system, Arabic RTL composition, and small JSON catalog/cart routes. The starter includes customers, a single seeded super-admin, categories, products, persisted registered carts, shipping rates, orders, and order-item snapshots.

## Business rules

- Cash on delivery only; an order-level database check constraint enforces it.
- Checkout requires a phone and an Egyptian governorate.
- Shipping rates resolve by exact governorate + city + area first, then city, then governorate.
- Checkout rechecks available stock and conditionally decrements each product within the order transaction.
- Order lines keep product name, SKU, price, quantity, and line total as snapshots.
- Order numbers are unique and generated as `ORD-YYYYMMDD-000001` after the order row is created.
- Admin creation is seed-only; there is no admin registration or admin-management endpoint.
- Guest carts live in the signed session; registered customer carts are persisted and merge at sign-in.

## Design decisions

Nile Modernism direction uses deep ink `#16211F`, Nile jade `#0E7667`, saffron `#D6A34A`, papyrus `#F5F0E8`, and clay `#C96E52`. The storefront is Arabic-first and RTL, with a desktop editorial split hero, horizontal category rail, product cards, and a cart summary. CSS-made product art acts as a placeholder until real images are uploaded.

## Operational limits and assumptions

- Seeded shipping rates and demo products are examples, not commercial commitments; edit them before taking orders.
- SQLite is suitable for the initial single-service starter, not intended for multi-worker concurrent production use.
- Uploads are local files, bounded to 5 MiB and limited to allowed image file extensions.
- Password reset produces a one-hour signed link and logs it; email sending is not configured.
- No online payment gateway, card fields, payment credentials, or checkout payments are included.
