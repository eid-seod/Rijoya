import { BarChart3, ChevronLeft, CircleDollarSign, LayoutDashboard, Package, Settings2, Store, Users } from "lucide-react";
import { Link, useLocation } from "wouter";
import type { PropsWithChildren, ReactNode } from "react";

export function OperationsLayout({ children, role }: PropsWithChildren<{ role: "vendor" | "admin" }>) {
  const [location] = useLocation();
  const isAdmin = role === "admin";
  const links = isAdmin ? [
    { href: "/admin", label: "Overview", icon: LayoutDashboard },
    { href: "/admin#vendors", label: "Vendors", icon: Store },
    { href: "/admin#orders", label: "Orders", icon: Package },
    { href: "/admin#reports", label: "Reports", icon: BarChart3 },
  ] : [
    { href: "/vendor/dashboard", label: "Overview", icon: LayoutDashboard },
    { href: "/vendor/dashboard#products", label: "Products", icon: Package },
    { href: "/vendor/dashboard#orders", label: "Orders", icon: CircleDollarSign },
    { href: "/vendor/dashboard#settings", label: "Settings", icon: Settings2 },
  ];
  return <div className="min-h-screen bg-[#f0eee8] text-[#20241f]"><aside className="fixed inset-y-0 left-0 hidden w-64 flex-col border-r border-[#20241f]/10 bg-[#20241f] text-[#f6f3ee] md:flex"><div className="flex h-20 items-center gap-3 border-b border-white/10 px-7"><span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#d9e7d2] font-black text-[#20241f]">R</span><span className="font-serif text-2xl">rijoya</span></div><div className="px-7 pt-8"><p className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#d9e7d2]">{isAdmin ? "Admin studio" : "Maker studio"}</p><p className="mt-2 text-sm text-white/50">{isAdmin ? "The pulse of the marketplace" : "Your shop, in one place"}</p></div><nav className="mt-9 flex-1 space-y-1 px-4">{links.map(link => { const Icon = link.icon; const active = location === link.href.split("#")[0] && (link.href.endsWith("#vendors") ? false : true); return <Link key={link.href} href={link.href} className={`flex items-center gap-3 rounded-xl px-3 py-3 text-sm transition ${active ? "bg-[#f6f3ee] font-bold text-[#20241f]" : "text-white/60 hover:bg-white/10 hover:text-white"}`}><Icon size={17} />{link.label}</Link>; })}</nav><div className="border-t border-white/10 p-5"><Link href="/" className="flex items-center gap-2 text-sm text-white/60 hover:text-white"><ChevronLeft size={16} /> Back to storefront</Link></div></aside><div className="md:pl-64"><header className="flex h-20 items-center justify-between border-b border-[#20241f]/10 bg-[#f6f3ee] px-5 sm:px-8"><div><p className="text-xs font-bold uppercase tracking-[0.18em] text-[#e35f36]">{isAdmin ? "Operations" : "Vendor workspace"}</p><h1 className="mt-1 font-serif text-2xl">{isAdmin ? "Good morning, team." : "Build your next best seller."}</h1></div><div className="flex items-center gap-3"><span className="hidden text-xs text-[#77776f] sm:block">Live preview</span><span className="h-2 w-2 rounded-full bg-[#81a873]" /></div></header><main className="p-5 sm:p-8">{children}</main></div></div>;
}

export function StatCard({ label, value, note, icon: Icon, accent = "#d9e7d2" }: { label: string; value: string; note: string; icon: React.ComponentType<{ size?: number }>; accent?: string }) {
  return <div className="rounded-[1.25rem] border border-[#20241f]/8 bg-[#f6f3ee] p-5 shadow-sm"><div className="flex items-start justify-between"><p className="text-xs font-bold uppercase tracking-[0.16em] text-[#77776f]">{label}</p><span style={{ backgroundColor: accent }} className="flex h-9 w-9 items-center justify-center rounded-xl"><Icon size={17} /></span></div><p className="mt-6 font-serif text-4xl">{value}</p><p className="mt-2 text-xs text-[#77776f]">{note}</p></div>;
}

export function SectionHeading({ eyebrow, title, action }: { eyebrow: string; title: string; action?: ReactNode }) {
  return <div className="mb-5 flex items-end justify-between gap-4"><div><p className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#e35f36]">{eyebrow}</p><h2 className="mt-2 font-serif text-3xl">{title}</h2></div>{action}</div>;
}
