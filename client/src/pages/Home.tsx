import { ProductCard, type MarketplaceProduct } from "@/components/MarketplaceShell";
import { Button } from "@/components/ui/button";
import { trpc } from "@/lib/trpc";
import { ArrowDownRight, ArrowUpRight, Compass, Leaf, Sparkles } from "lucide-react";
import { Link } from "wouter";

const categoryTiles = [
  { name: "Home", note: "Objects with a point of view", tone: "bg-[#d9e7d2]" },
  { name: "Wellness", note: "Small rituals, better days", tone: "bg-[#f2c7a8]" },
  { name: "Accessories", note: "The pieces you reach for", tone: "bg-[#d9d2e7]" },
];

export default function Home() {
  const { data: featured } = trpc.catalog.featured.useQuery();
  const products = (featured ?? []) as MarketplaceProduct[];
  return <>
    <section className="container grid min-h-[620px] items-center gap-10 py-12 lg:grid-cols-[0.95fr_1.05fr] lg:py-20">
      <div className="relative z-10 max-w-xl">
        <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-[#20241f]/15 px-3 py-2 text-[11px] font-bold uppercase tracking-[0.2em]"><Sparkles size={13} className="text-[#e35f36]" /> The good edit</div>
        <h1 className="font-serif text-[clamp(3.6rem,8vw,7.4rem)] leading-[0.88] tracking-[-0.07em]">Made by<br /><span className="text-[#e35f36]">someone.</span></h1>
        <p className="mt-8 max-w-md text-lg leading-8 text-[#62665d]">A brighter kind of marketplace for considered goods, small-batch finds, and the people who make them.</p>
        <div className="mt-9 flex flex-wrap items-center gap-4"><Button asChild size="lg" className="h-12 rounded-full bg-[#20241f] px-7 text-sm font-bold hover:bg-[#e35f36]"><Link href="/catalog">Shop the edit <ArrowUpRight size={16} /></Link></Button><Link href="#story" className="inline-flex items-center gap-2 text-sm font-bold">Why Rijoya <ArrowDownRight size={15} /></Link></div>
        <div className="mt-14 flex items-center gap-8 border-t border-[#20241f]/15 pt-5 text-xs font-semibold uppercase tracking-[0.16em] text-[#77776f]"><span className="flex items-center gap-2"><Leaf size={16} className="text-[#66825d]" /> Independent</span><span className="flex items-center gap-2"><Compass size={16} className="text-[#e35f36]" /> Curated</span></div>
      </div>
      <div className="relative mx-auto w-full max-w-[620px]">
        <div className="absolute -left-6 top-12 z-10 rounded-full bg-[#e35f36] px-5 py-3 text-xs font-black uppercase tracking-[0.16em] text-white shadow-lg shadow-[#e35f36]/20">New / now</div>
        <div className="aspect-[0.86] overflow-hidden rounded-[2.5rem] bg-[#d9e7d2] shadow-2xl shadow-[#20241f]/10"><img src="https://images.unsplash.com/photo-1586023492125-27b2c045efd7?auto=format&fit=crop&w=1400&q=90" alt="Sunlit table with collected home goods" className="h-full w-full object-cover" /></div>
        <div className="absolute -bottom-8 -right-3 hidden max-w-[220px] rounded-[1.5rem] bg-[#f6f3ee] p-5 shadow-xl sm:block"><p className="font-serif text-2xl leading-tight">The art of choosing well.</p><p className="mt-3 text-xs leading-5 text-[#77776f]">Good things carry a little bit of where they came from.</p></div>
      </div>
    </section>

    <section className="container py-20"><div className="mb-8 flex items-end justify-between gap-5"><div><p className="text-xs font-bold uppercase tracking-[0.2em] text-[#e35f36]">Find your next favorite</p><h2 className="mt-2 font-serif text-4xl tracking-tight sm:text-5xl">Shop by feeling</h2></div><Link href="/catalog" className="hidden items-center gap-2 text-sm font-bold sm:flex">View all <ArrowUpRight size={16} /></Link></div><div className="grid gap-4 md:grid-cols-3">{categoryTiles.map((tile, index) => <Link href={`/catalog?category=${tile.name}`} key={tile.name} className={`group relative min-h-[240px] overflow-hidden rounded-[1.75rem] ${tile.tone} p-7 transition hover:-translate-y-1`}><span className="absolute -bottom-10 -right-8 h-44 w-44 rounded-full border-[20px] border-white/25 transition duration-500 group-hover:scale-125" /><span className="relative z-10 flex h-full flex-col justify-between"><span className="text-[11px] font-bold uppercase tracking-[0.2em]">0{index + 1}</span><span><h3 className="font-serif text-3xl">{tile.name}</h3><p className="mt-2 max-w-[170px] text-sm text-[#20241f]/65">{tile.note}</p></span></span></Link>)}</div></section>

    <section className="bg-[#e8e4db] py-20"><div className="container"><div className="mb-9 flex items-end justify-between gap-5"><div><p className="text-xs font-bold uppercase tracking-[0.2em] text-[#e35f36]">The short list</p><h2 className="mt-2 font-serif text-4xl tracking-tight sm:text-5xl">Good things, lately</h2></div><Link href="/catalog" className="hidden items-center gap-2 text-sm font-bold sm:flex">Shop all <ArrowUpRight size={16} /></Link></div>{products.length > 0 ? <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">{products.map(product => <ProductCard key={product.id} product={product} />)}</div> : <div className="rounded-3xl border border-dashed border-[#20241f]/20 p-10 text-center text-[#77776f]">Our next edit is being carefully assembled.</div>}</div></section>

    <section id="story" className="container grid gap-10 py-24 lg:grid-cols-[0.8fr_1.2fr] lg:items-end"><div><p className="text-xs font-bold uppercase tracking-[0.2em] text-[#e35f36]">A marketplace with a pulse</p><h2 className="mt-4 max-w-lg font-serif text-5xl leading-[0.95] tracking-tight sm:text-6xl">Less scroll.<br />More <em className="text-[#e35f36]">meaning.</em></h2></div><div className="grid gap-8 sm:grid-cols-2"><div className="border-t-2 border-[#20241f] pt-4"><p className="font-serif text-2xl">01 / Good origins</p><p className="mt-3 text-sm leading-6 text-[#77776f]">We make room for the story behind the object — the maker, the material, the why.</p></div><div className="border-t-2 border-[#20241f] pt-4"><p className="font-serif text-2xl">02 / A human edit</p><p className="mt-3 text-sm leading-6 text-[#77776f]">Independent brands deserve more than an algorithm. They deserve attention.</p></div></div></section>
  </>;
}
