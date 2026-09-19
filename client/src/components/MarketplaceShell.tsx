import { useAuth } from "@/_core/hooks/useAuth";
import { startLogin } from "@/const";
import { useCart, type CartProduct } from "@/contexts/CartContext";
import { Link } from "wouter";
import { ArrowUpRight, Heart, Menu, ShoppingBag, X } from "lucide-react";
import { useState, type PropsWithChildren } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export type MarketplaceProduct = CartProduct & {
  description?: string | null;
  inventory: number;
  vendorName?: string;
};

export function MarketplaceShell({ children }: PropsWithChildren) {
  const { count } = useCart();
  const { user, isAuthenticated, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  const signIn = () => startLogin();

  return (
    <div className="min-h-screen bg-[#f6f3ee] text-[#20241f]">
      <div className="bg-[#20241f] px-4 py-2 text-center text-[11px] font-semibold uppercase tracking-[0.22em] text-[#f6f3ee]">
        Free shipping on orders over $75 · Thoughtful goods, independent makers
      </div>
      <header className="sticky top-0 z-30 border-b border-[#20241f]/10 bg-[#f6f3ee]/95 backdrop-blur">
        <div className="container flex h-20 items-center justify-between gap-6">
          <Link href="/" className="flex items-center gap-3" onClick={() => setMenuOpen(false)}>
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[#d9e7d2] text-lg font-black text-[#20241f]">R</span>
            <span className="font-serif text-2xl font-semibold tracking-tight">rijoya</span>
          </Link>
          <nav className="hidden items-center gap-7 text-sm font-medium lg:flex">
            <Link href="/catalog" className="transition-colors hover:text-[#e35f36]">Shop</Link>
            <a href="#story" className="transition-colors hover:text-[#e35f36]">Our story</a>
            <Link href="/vendor/register" className="transition-colors hover:text-[#e35f36]">Sell on Rijoya</Link>
          </nav>
          <div className="flex items-center gap-2">
            <button aria-label="Favorites" onClick={() => toast.info("Favorites are coming soon.")} className="hidden rounded-full p-2.5 transition hover:bg-[#e7e3db] sm:inline-flex"><Heart size={18} strokeWidth={1.8} /></button>
            {isAuthenticated ? (
              <button onClick={() => void logout()} className="hidden text-sm font-semibold sm:block">Hi, {user?.name?.split(" ")[0] ?? "there"}</button>
            ) : (
              <button onClick={signIn} className="hidden text-sm font-semibold sm:block">Sign in</button>
            )}
            <Link href="/cart" className="relative rounded-full p-2.5 transition hover:bg-[#e7e3db]" aria-label="Cart">
              <ShoppingBag size={19} strokeWidth={1.8} />
              {count > 0 && <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-[#e35f36] px-1 text-[10px] font-bold text-white">{count}</span>}
            </Link>
            <button aria-label="Open menu" onClick={() => setMenuOpen(value => !value)} className="rounded-full p-2.5 transition hover:bg-[#e7e3db] lg:hidden">{menuOpen ? <X size={19} /> : <Menu size={19} />}</button>
          </div>
        </div>
        {menuOpen && <div className="border-t border-[#20241f]/10 px-5 py-5 lg:hidden"><div className="flex flex-col gap-4 text-sm font-semibold"><Link href="/catalog" onClick={() => setMenuOpen(false)}>Shop all</Link><a href="#story" onClick={() => setMenuOpen(false)}>Our story</a><Link href="/vendor/register" onClick={() => setMenuOpen(false)}>Sell on Rijoya</Link>{isAuthenticated ? <button className="text-left" onClick={() => void logout()}>Sign out</button> : <button className="text-left" onClick={signIn}>Sign in</button>}</div></div>}
      </header>
      <main>{children}</main>
      <footer className="mt-20 bg-[#20241f] text-[#f6f3ee]">
        <div className="container grid gap-10 py-14 md:grid-cols-[1.3fr_1fr_1fr_1fr]">
          <div><div className="font-serif text-3xl">rijoya</div><p className="mt-4 max-w-xs text-sm leading-6 text-[#f6f3ee]/65">A considered marketplace for the makers, objects, and rituals that make a place feel like yours.</p></div>
          <div><p className="mb-4 text-xs font-bold uppercase tracking-[0.2em] text-[#d9e7d2]">Explore</p><div className="space-y-3 text-sm text-[#f6f3ee]/70"><Link href="/catalog" className="block hover:text-white">All products</Link><Link href="/vendor/register" className="block hover:text-white">Become a vendor</Link><a href="#story" className="block hover:text-white">Our story</a></div></div>
          <div><p className="mb-4 text-xs font-bold uppercase tracking-[0.2em] text-[#d9e7d2]">Help</p><div className="space-y-3 text-sm text-[#f6f3ee]/70"><button className="block" onClick={() => toast.info("Returns support is coming soon.")}>Shipping & returns</button><button className="block" onClick={() => toast.info("Support is coming soon.")}>Contact us</button></div></div>
          <div><p className="mb-4 text-xs font-bold uppercase tracking-[0.2em] text-[#d9e7d2]">For makers</p><p className="text-sm leading-6 text-[#f6f3ee]/70">Bring your point of view to a marketplace built around independent craft.</p><Link href="/vendor/register" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-[#f2a88f]">Start selling <ArrowUpRight size={14} /></Link></div>
        </div>
        <div className="border-t border-white/10"><div className="container flex flex-col justify-between gap-3 py-5 text-xs text-[#f6f3ee]/45 sm:flex-row"><span>© 2026 Rijoya Marketplace</span><span>Secure checkout · Independent commerce</span></div></div>
      </footer>
    </div>
  );
}

export function ProductCard({ product }: { product: MarketplaceProduct }) {
  const { add } = useCart();
  const image = product.imageUrl || "https://images.unsplash.com/photo-1494438639946-1ebd1d20bf85?auto=format&fit=crop&w=900&q=85";
  const vendor = product.vendorName || "Independent maker";
  return <article className="group">
    <div className="relative aspect-[4/5] overflow-hidden rounded-[1.75rem] bg-[#e6e1d8]">
      <img src={image} alt={product.name} className="h-full w-full object-cover transition duration-500 group-hover:scale-105" />
      <div className="absolute left-4 top-4"><Badge className="border-0 bg-[#f6f3ee]/90 text-[#20241f]">{product.category}</Badge></div>
      <button aria-label={`Save ${product.name}`} onClick={() => toast.info("Favorites are coming soon.")} className="absolute right-4 top-4 rounded-full bg-[#f6f3ee]/90 p-2.5 opacity-0 shadow-sm transition group-hover:opacity-100"><Heart size={16} /></button>
      <button onClick={() => { add({ id: product.id, vendorId: product.vendorId, name: product.name, price: Number(product.price), imageUrl: image, category: product.category }); toast.success(`${product.name} added to bag`); }} className="absolute inset-x-4 bottom-4 translate-y-2 rounded-full bg-[#20241f] py-3 text-sm font-bold text-white opacity-0 transition duration-300 hover:bg-[#e35f36] group-hover:translate-y-0 group-hover:opacity-100">Add to bag</button>
    </div>
    <div className="flex items-start justify-between gap-3 px-1 pt-4"><div><p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#77776f]">{vendor}</p><h3 className="mt-1 font-serif text-xl leading-tight">{product.name}</h3></div><p className="pt-1 text-sm font-bold">${Number(product.price).toFixed(2)}</p></div>
  </article>;
}
