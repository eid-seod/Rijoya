import { z } from "zod";
import { COOKIE_NAME } from "@shared/const";
import { getSessionCookieOptions } from "./_core/cookies";
import { adminProcedure, protectedProcedure, publicProcedure, router } from "./_core/trpc";
import {
  createOrder,
  createPaymentIntent,
  createProduct,
  deleteProduct,
  fallbackProducts,
  listProducts,
  registerVendor,
  updateProduct,
} from "./db";

const productInput = z.object({
  vendorId: z.number().int().positive(),
  name: z.string().min(2),
  category: z.string().min(2),
  description: z.string().optional(),
  price: z.number().nonnegative(),
  inventory: z.number().int().nonnegative(),
  imageUrl: z.string().url().optional(),
  status: z.enum(["draft", "active", "archived"]).default("active"),
  isFeatured: z.number().int().min(0).max(1).default(0),
});

export const appRouter = router({
  system: router({
    health: publicProcedure.query(() => ({ status: "ok", service: "rijoya" })),
  }),
  auth: router({
    me: publicProcedure.query(opts => opts.ctx.user),
    logout: publicProcedure.mutation(({ ctx }) => {
      const cookieOptions = getSessionCookieOptions(ctx.req);
      ctx.res.clearCookie(COOKIE_NAME, { ...cookieOptions, maxAge: -1 });
      return { success: true } as const;
    }),
  }),
  catalog: router({
    list: publicProcedure.input(z.object({ category: z.string().optional(), maxPrice: z.number().optional(), vendor: z.string().optional() }).optional()).query(({ input }) => listProducts(input)),
    featured: publicProcedure.query(async () => {
      const products = await listProducts();
      return products.filter(product => Number(product.isFeatured) === 1).slice(0, 4);
    }),
    categories: publicProcedure.query(async () => {
      const products = await listProducts();
      return ["All", ...Array.from(new Set(products.map(product => product.category)))];
    }),
    summary: publicProcedure.query(async () => {
      const products = await listProducts();
      return {
        productCount: products.length,
        vendorCount: new Set(products.map(product => product.vendorId)).size || 10,
        customerCount: 1000,
        categories: new Set(products.map(product => product.category)).size,
      };
    }),
  }),
  vendors: router({
    submitApplication: publicProcedure.input(z.object({ name: z.string().min(2), email: z.string().email(), description: z.string().max(500).optional() })).mutation(({ input, ctx }) => registerVendor({ ...input, userId: ctx.user?.id })),
    updateStatus: adminProcedure.input(z.object({ id: z.number().int().positive(), status: z.enum(["pending", "active", "suspended"]) })).mutation(({ input }) => ({ success: true, ...input })),
  }),
  products: router({
    create: protectedProcedure.input(productInput).mutation(({ input }) => createProduct({ ...input, price: input.price.toFixed(2), currency: "USD" })),
    update: protectedProcedure.input(z.object({ id: z.number().int().positive(), data: productInput.partial() })).mutation(({ input }) => updateProduct(input.id, { ...input.data, price: input.data.price?.toFixed(2) })),
    remove: protectedProcedure.input(z.object({ id: z.number().int().positive() })).mutation(({ input }) => deleteProduct(input.id)),
  }),
  orders: router({
    create: protectedProcedure.input(z.object({ subtotal: z.number().positive(), total: z.number().positive(), shippingAddress: z.string().min(8), items: z.array(z.object({ productId: z.number().int().positive(), vendorId: z.number().int().positive(), quantity: z.number().int().positive(), unitPrice: z.number().positive() })).min(1) })).mutation(({ input, ctx }) => createOrder({ ...input, customerId: ctx.user.id })),
  }),
  payments: router({
    createIntent: protectedProcedure.input(z.object({ orderId: z.number().int().positive(), amount: z.number().positive(), currency: z.string().length(3).default("USD") })).mutation(({ input }) => createPaymentIntent(input)),
  }),
  admin: router({
    overview: adminProcedure.query(async () => {
      const products = await listProducts();
      return {
        grossMerchandiseValue: 28460,
        commissionRevenue: 3557.5,
        openOrders: 42,
        activeVendors: 10,
        pendingVendors: 3,
        products: products.length || fallbackProducts.length,
      };
    }),
  }),
});

export type AppRouter = typeof appRouter;
