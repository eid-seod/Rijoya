import {
  decimal,
  index,
  int,
  mysqlEnum,
  mysqlTable,
  text,
  timestamp,
  varchar,
} from "drizzle-orm/mysql-core";

/** Core identity table used by Manus OAuth. */
export const users = mysqlTable("users", {
  id: int("id").autoincrement().primaryKey(),
  openId: varchar("openId", { length: 64 }).notNull().unique(),
  name: text("name"),
  email: varchar("email", { length: 320 }),
  loginMethod: varchar("loginMethod", { length: 64 }),
  role: mysqlEnum("role", ["user", "admin"]).default("user").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
  lastSignedIn: timestamp("lastSignedIn").defaultNow().notNull(),
});

export const vendors = mysqlTable(
  "vendors",
  {
    id: int("id").autoincrement().primaryKey(),
    userId: int("userId"),
    name: varchar("name", { length: 160 }).notNull(),
    slug: varchar("slug", { length: 180 }).notNull().unique(),
    email: varchar("email", { length: 320 }).notNull(),
    description: text("description"),
    status: mysqlEnum("status", ["pending", "active", "suspended"]).default("pending").notNull(),
    commissionRate: decimal("commissionRate", { precision: 5, scale: 2 }).default("12.50").notNull(),
    createdAt: timestamp("createdAt").defaultNow().notNull(),
    updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
  },
  table => ({ userIdx: index("vendors_user_idx").on(table.userId) })
);

export const products = mysqlTable(
  "products",
  {
    id: int("id").autoincrement().primaryKey(),
    vendorId: int("vendorId").notNull(),
    name: varchar("name", { length: 180 }).notNull(),
    slug: varchar("slug", { length: 200 }).notNull().unique(),
    category: varchar("category", { length: 80 }).notNull(),
    description: text("description"),
    price: decimal("price", { precision: 12, scale: 2 }).notNull(),
    currency: varchar("currency", { length: 3 }).default("USD").notNull(),
    inventory: int("inventory").default(0).notNull(),
    imageUrl: varchar("imageUrl", { length: 500 }),
    status: mysqlEnum("status", ["draft", "active", "archived"]).default("active").notNull(),
    isFeatured: int("isFeatured").default(0).notNull(),
    createdAt: timestamp("createdAt").defaultNow().notNull(),
    updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
  },
  table => ({ vendorIdx: index("products_vendor_idx").on(table.vendorId), categoryIdx: index("products_category_idx").on(table.category) })
);

export const orders = mysqlTable(
  "orders",
  {
    id: int("id").autoincrement().primaryKey(),
    customerId: int("customerId").notNull(),
    status: mysqlEnum("status", ["pending", "paid", "processing", "shipped", "completed", "cancelled"]).default("pending").notNull(),
    subtotal: decimal("subtotal", { precision: 12, scale: 2 }).notNull(),
    commission: decimal("commission", { precision: 12, scale: 2 }).default("0.00").notNull(),
    total: decimal("total", { precision: 12, scale: 2 }).notNull(),
    currency: varchar("currency", { length: 3 }).default("USD").notNull(),
    shippingAddress: text("shippingAddress"),
    createdAt: timestamp("createdAt").defaultNow().notNull(),
    updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
  },
  table => ({ customerIdx: index("orders_customer_idx").on(table.customerId), statusIdx: index("orders_status_idx").on(table.status) })
);

export const orderItems = mysqlTable(
  "orderItems",
  {
    id: int("id").autoincrement().primaryKey(),
    orderId: int("orderId").notNull(),
    productId: int("productId").notNull(),
    vendorId: int("vendorId").notNull(),
    quantity: int("quantity").notNull(),
    unitPrice: decimal("unitPrice", { precision: 12, scale: 2 }).notNull(),
    lineTotal: decimal("lineTotal", { precision: 12, scale: 2 }).notNull(),
  },
  table => ({ orderIdx: index("order_items_order_idx").on(table.orderId), vendorIdx: index("order_items_vendor_idx").on(table.vendorId) })
);

export const payments = mysqlTable(
  "payments",
  {
    id: int("id").autoincrement().primaryKey(),
    orderId: int("orderId").notNull(),
    provider: varchar("provider", { length: 40 }).default("demo").notNull(),
    providerPaymentId: varchar("providerPaymentId", { length: 180 }),
    status: mysqlEnum("status", ["requires_payment_method", "requires_confirmation", "succeeded", "failed", "refunded"]).default("requires_payment_method").notNull(),
    amount: decimal("amount", { precision: 12, scale: 2 }).notNull(),
    currency: varchar("currency", { length: 3 }).default("USD").notNull(),
    createdAt: timestamp("createdAt").defaultNow().notNull(),
    updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
  },
  table => ({ orderIdx: index("payments_order_idx").on(table.orderId) })
);

export type User = typeof users.$inferSelect;
export type InsertUser = typeof users.$inferInsert;
export type Vendor = typeof vendors.$inferSelect;
export type InsertVendor = typeof vendors.$inferInsert;
export type Product = typeof products.$inferSelect;
export type InsertProduct = typeof products.$inferInsert;
export type Order = typeof orders.$inferSelect;
export type InsertOrder = typeof orders.$inferInsert;
export type OrderItem = typeof orderItems.$inferSelect;
export type Payment = typeof payments.$inferSelect;
