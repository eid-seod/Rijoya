import { desc, eq } from "drizzle-orm";
import { drizzle } from "drizzle-orm/mysql2";
import {
  InsertProduct,
  InsertUser,
  products,
  users,
  vendors,
  orders,
  orderItems,
  payments,
} from "../drizzle/schema";
import { ENV } from "./_core/env";

let _db: ReturnType<typeof drizzle> | null = null;

export async function getDb() {
  if (!_db && process.env.DATABASE_URL) {
    try {
      _db = drizzle(process.env.DATABASE_URL);
    } catch (error) {
      console.warn("[Database] Failed to connect:", error);
      _db = null;
    }
  }
  return _db;
}

export async function upsertUser(user: InsertUser): Promise<void> {
  if (!user.openId) throw new Error("User openId is required for upsert");
  const db = await getDb();
  if (!db) {
    console.warn("[Database] Cannot upsert user: database not available");
    return;
  }

  const values: InsertUser = { openId: user.openId };
  const updateSet: Record<string, unknown> = {};
  const textFields = ["name", "email", "loginMethod"] as const;
  for (const field of textFields) {
    if (user[field] !== undefined) {
      values[field] = user[field] ?? null;
      updateSet[field] = user[field] ?? null;
    }
  }
  if (user.lastSignedIn !== undefined) {
    values.lastSignedIn = user.lastSignedIn;
    updateSet.lastSignedIn = user.lastSignedIn;
  }
  if (user.role !== undefined || user.openId === ENV.ownerOpenId) {
    values.role = user.role ?? "admin";
    updateSet.role = values.role;
  }
  values.lastSignedIn ??= new Date();
  updateSet.lastSignedIn ??= new Date();
  await db.insert(users).values(values).onDuplicateKeyUpdate({ set: updateSet });
}

export async function getUserByOpenId(openId: string) {
  const db = await getDb();
  if (!db) return undefined;
  const result = await db.select().from(users).where(eq(users.openId, openId)).limit(1);
  return result[0];
}

export const fallbackProducts = [
  { id: 1, vendorId: 1, name: "Arc Desk Lamp", slug: "arc-desk-lamp", category: "Home", description: "Soft light, sculptural silhouette, and a warm brass finish for slower evenings.", price: 84, currency: "USD", inventory: 24, imageUrl: "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=900&q=85", status: "active", isFeatured: 1, vendorName: "Mara Studio" },
  { id: 2, vendorId: 2, name: "Field Notes Tote", slug: "field-notes-tote", category: "Accessories", description: "A durable everyday carry woven from recycled cotton canvas.", price: 46, currency: "USD", inventory: 68, imageUrl: "https://images.unsplash.com/photo-1544816155-12df9643f363?auto=format&fit=crop&w=900&q=85", status: "active", isFeatured: 1, vendorName: "Woven North" },
  { id: 3, vendorId: 3, name: "Cedar + Smoke Candle", slug: "cedar-smoke-candle", category: "Wellness", description: "A grounded blend of cedarwood, amber, and a quiet trace of smoke.", price: 28, currency: "USD", inventory: 41, imageUrl: "https://images.unsplash.com/photo-1603006905003-be475563bc59?auto=format&fit=crop&w=900&q=85", status: "active", isFeatured: 1, vendorName: "Kindred Objects" },
  { id: 4, vendorId: 4, name: "Alba Ceramic Mug", slug: "alba-ceramic-mug", category: "Kitchen", description: "Hand-thrown stoneware with a milky glaze and a generous handle.", price: 32, currency: "USD", inventory: 19, imageUrl: "https://images.unsplash.com/photo-1514228742587-6b1558fcca3d?auto=format&fit=crop&w=900&q=85", status: "active", isFeatured: 0, vendorName: "Alba Ceramics" },
  { id: 5, vendorId: 5, name: "Sol Linen Throw", slug: "sol-linen-throw", category: "Textiles", description: "Washed linen in a sun-faded ochre for the end of the bed or sofa.", price: 118, currency: "USD", inventory: 12, imageUrl: "https://images.unsplash.com/photo-1584100936595-c0654b55a2e2?auto=format&fit=crop&w=900&q=85", status: "active", isFeatured: 0, vendorName: "Sol House" },
  { id: 6, vendorId: 6, name: "Reform Leather Wallet", slug: "reform-leather-wallet", category: "Accessories", description: "Slim vegetable-tanned leather, made to age beautifully.", price: 64, currency: "USD", inventory: 32, imageUrl: "https://images.unsplash.com/photo-1627123424574-724758594e93?auto=format&fit=crop&w=900&q=85", status: "active", isFeatured: 0, vendorName: "Reform Goods" },
];

export async function listProducts(filters?: { category?: string; maxPrice?: number; vendor?: string }) {
  const db = await getDb();
  if (!db) {
    return fallbackProducts.filter(product =>
      (!filters?.category || filters.category === "All" || product.category === filters.category) &&
      (!filters?.maxPrice || product.price <= filters.maxPrice) &&
      (!filters?.vendor || product.vendorName.toLowerCase().includes(filters.vendor.toLowerCase()))
    );
  }
  const rows = await db.select().from(products).orderBy(desc(products.createdAt)).limit(100);
  const source = rows.length > 0 ? rows : fallbackProducts;
  return source.filter(product =>
    (!filters?.category || filters.category === "All" || product.category === filters.category) &&
    (!filters?.maxPrice || Number(product.price) <= filters.maxPrice)
  );
}

export async function registerVendor(input: { name: string; email: string; description?: string; userId?: number }) {
  const db = await getDb();
  if (!db) return { success: true, status: "pending" as const, demo: true };
  const slug = `${input.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${Date.now()}`;
  await db.insert(vendors).values({ name: input.name, slug, email: input.email, description: input.description, userId: input.userId, status: "pending" });
  return { success: true, status: "pending" as const, demo: false };
}

export async function createProduct(input: Omit<InsertProduct, "slug"> & { slug?: string }) {
  const db = await getDb();
  if (!db) return { success: true, demo: true };
  const slug = input.slug ?? `${input.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${Date.now()}`;
  await db.insert(products).values({ ...input, slug });
  return { success: true, demo: false };
}

export async function updateProduct(id: number, input: Partial<InsertProduct>) {
  const db = await getDb();
  if (!db) return { success: true, demo: true };
  await db.update(products).set(input).where(eq(products.id, id));
  return { success: true, demo: false };
}

export async function deleteProduct(id: number) {
  const db = await getDb();
  if (!db) return { success: true, demo: true };
  await db.delete(products).where(eq(products.id, id));
  return { success: true, demo: false };
}

export async function createOrder(input: { customerId: number; subtotal: number; total: number; shippingAddress?: string; items: Array<{ productId: number; vendorId: number; quantity: number; unitPrice: number }> }) {
  const db = await getDb();
  if (!db) return { success: true, orderId: 1001, demo: true };
  const inserted = await db.insert(orders).values({ customerId: input.customerId, subtotal: input.subtotal.toFixed(2), total: input.total.toFixed(2), commission: (input.subtotal * 0.125).toFixed(2), shippingAddress: input.shippingAddress, status: "pending" });
  const orderId = Number(inserted[0]?.insertId ?? 0);
  if (orderId) {
    await db.insert(orderItems).values(input.items.map(item => ({ orderId, productId: item.productId, vendorId: item.vendorId, quantity: item.quantity, unitPrice: item.unitPrice.toFixed(2), lineTotal: (item.unitPrice * item.quantity).toFixed(2) })));
  }
  return { success: true, orderId, demo: false };
}

export async function createPaymentIntent(input: { orderId: number; amount: number; currency?: string }) {
  const db = await getDb();
  if (!db) return { success: true, paymentId: `demo_pi_${input.orderId}`, status: "requires_confirmation" as const, demo: true };
  const inserted = await db.insert(payments).values({ orderId: input.orderId, amount: input.amount.toFixed(2), currency: input.currency ?? "USD", provider: "demo", status: "requires_confirmation" });
  return { success: true, paymentId: `payment_${Number(inserted[0]?.insertId ?? 0)}`, status: "requires_confirmation" as const, demo: false };
}
