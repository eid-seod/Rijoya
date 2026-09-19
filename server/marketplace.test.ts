import { describe, expect, it } from "vitest";
import { appRouter } from "./routers";
import type { TrpcContext } from "./_core/context";

function createPublicContext(): TrpcContext {
  return {
    user: null,
    req: { protocol: "https", headers: {} } as TrpcContext["req"],
    res: {} as TrpcContext["res"],
  };
}

describe("marketplace catalog", () => {
  it("returns a curated catalog for the storefront", async () => {
    const caller = appRouter.createCaller(createPublicContext());
    const products = await caller.catalog.list();
    expect(products.length).toBeGreaterThan(0);
    expect(products[0]).toMatchObject({ name: expect.any(String), category: expect.any(String) });
  });

  it("returns featured products and category filters", async () => {
    const caller = appRouter.createCaller(createPublicContext());
    const [featured, categories] = await Promise.all([
      caller.catalog.featured(),
      caller.catalog.categories(),
    ]);
    expect(featured.length).toBeGreaterThan(0);
    expect(categories).toContain("All");
    expect(categories.length).toBeGreaterThan(1);
  });
});

describe("system health", () => {
  it("reports the Rijoya API as healthy", async () => {
    const caller = appRouter.createCaller(createPublicContext());
    await expect(caller.system.health()).resolves.toEqual({ status: "ok", service: "rijoya" });
  });
});
