# Rijoya Marketplace MVP

Rijoya is a multi-vendor marketplace skeleton for the Phase 1 launch. The current product includes a customer storefront, catalog filters, cart, checkout flow, vendor onboarding, vendor workspace, and admin operations dashboard.

## Runtime note

The managed WebDev runtime available for this session provisions a React + TypeScript frontend with an Express/tRPC server and Drizzle-backed MySQL/TiDB database. It does not provide a deployable Flask/PostgreSQL runtime. The implementation therefore uses the platform-supported full-stack stack so the site, authentication, database, and preview can run together. The domain model and API boundaries remain portable to Flask/PostgreSQL if that infrastructure is introduced in a later deployment phase.

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Public home page, categories, featured products, maker story |
| `/catalog` | Product listing with category, price, and maker filters |
| `/cart` | Persistent cart with quantity controls and totals |
| `/checkout` | Shipping details, order creation, and payment-intent handoff |
| `/vendor/register` | Vendor application form |
| `/vendor/dashboard` | Product upload form, sales pulse, order activity, KPI cards |
| `/admin` | GMV, commissions, vendors, open orders, category mix, and queue cards |

## API procedures

The server exposes typed tRPC procedures under `/api/trpc`:

- `auth.me` and `auth.logout`
- `catalog.list`, `catalog.featured`, `catalog.categories`, `catalog.summary`
- `vendors.submitApplication` and `vendors.updateStatus`
- `products.create`, `products.update`, and `products.remove`
- `orders.create`
- `payments.createIntent`
- `admin.overview`

Authentication uses the scaffolded Manus OAuth flow. Protected product, order, payment, and admin procedures use the existing `protectedProcedure` and `adminProcedure` guards.

## Database schema

The generated and applied migration creates:

- `users`
- `vendors`
- `products`
- `orders`
- `orderItems`
- `payments`

Indexes cover vendor ownership, product category, customer orders, payment lookup, and operational status queries. Monetary values use fixed-precision decimal columns. Timestamps are UTC-managed database timestamps.

## Payment status

Checkout currently creates a server-side payment intent using the `demo` provider. This keeps the MVP flow testable without committing credentials or processing real money. To move to production payments, add a provider integration (for example Stripe), set its server-side secret, replace the `createPaymentIntent` provider implementation, and add webhook verification before enabling live checkout.

## Verification

The verified build loop is:

```text
pnpm check  ✅
pnpm test   ✅  4 tests passing
pnpm build  ✅
```

The managed database migration was applied successfully, and the live preview was visually checked for the storefront, catalog, cart, vendor registration, vendor workspace, and admin workspace.
