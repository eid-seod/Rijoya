import { useAuth } from "@/_core/hooks/useAuth";
import { startLogin } from "@/const";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCart } from "@/contexts/CartContext";
import { trpc } from "@/lib/trpc";
import { ArrowLeft, ArrowRight, Check, LockKeyhole } from "lucide-react";
import { useState } from "react";
import { Link } from "wouter";
import { toast } from "sonner";

export default function Checkout() {
  const { items, total, clear } = useCart();
  const { isAuthenticated } = useAuth();
  const [address, setAddress] = useState("");
  const [complete, setComplete] = useState<number | null>(null);
  const order = trpc.orders.create.useMutation();
  const payment = trpc.payments.createIntent.useMutation();
  const grandTotal = total >= 75 ? total : total + 6;
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!isAuthenticated) { startLogin(); return; }
    try {
      const created = await order.mutateAsync({ subtotal: total, total: grandTotal, shippingAddress: address, items: items.map(item => ({ productId: item.id, vendorId: item.vendorId, quantity: item.quantity, unitPrice: Number(item.price) })) });
      await payment.mutateAsync({ orderId: created.orderId, amount: grandTotal });
      setComplete(created.orderId);
      clear();
      toast.success("Order placed");
    } catch { toast.error("We couldn't place that order. Please try again."); }
  };
  if (complete) return <div className="container flex min-h-[620px] items-center justify-center py-16"><div className="max-w-lg text-center"><div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[#d9e7d2]"><Check size={30} /></div><p className="mt-8 text-xs font-bold uppercase tracking-[0.2em] text-[#e35f36]">Order #{complete}</p><h1 className="mt-3 font-serif text-6xl leading-none">On its<br /><em>way to you.</em></h1><p className="mx-auto mt-6 max-w-md leading-7 text-[#77776f]">Your order is in the queue. You’ll receive an update when your makers begin preparing it.</p><Button asChild className="mt-8 rounded-full bg-[#20241f] px-7 hover:bg-[#e35f36]"><Link href="/catalog">Keep exploring <ArrowRight size={16} /></Link></Button></div></div>;
  if (items.length === 0) return <div className="container py-24 text-center"><h1 className="font-serif text-5xl">Your bag is empty.</h1><Button asChild className="mt-6 rounded-full"><Link href="/catalog">Back to shop</Link></Button></div>;
  return <div className="container max-w-6xl py-12 sm:py-16"><Link href="/cart" className="inline-flex items-center gap-2 text-sm font-semibold text-[#77776f] hover:text-[#20241f]"><ArrowLeft size={15} /> Back to bag</Link><div className="mt-10 grid gap-12 lg:grid-cols-[1fr_360px]"><div><p className="text-xs font-bold uppercase tracking-[0.2em] text-[#e35f36]">Almost yours</p><h1 className="mt-3 font-serif text-6xl tracking-[-0.05em]">Checkout.</h1><form onSubmit={submit} className="mt-10 space-y-8"><section><div className="mb-4 flex items-center justify-between"><h2 className="font-serif text-2xl">Shipping details</h2><span className="text-xs text-[#77776f]">Step 1 of 1</span></div><div className="grid gap-4 sm:grid-cols-2"><label className="text-sm sm:col-span-2"><span className="mb-2 block text-[#77776f]">Address</span><Input required value={address} onChange={event => setAddress(event.target.value)} placeholder="123 Market Street, City, Country" /></label></div></section><section className="rounded-[1.5rem] border border-[#20241f]/12 bg-[#e8e4db] p-5"><div className="flex items-start gap-3"><LockKeyhole size={18} className="mt-0.5 text-[#e35f36]" /><div><h2 className="text-sm font-bold">Secure payment</h2><p className="mt-1 text-sm leading-6 text-[#77776f]">Payment integration is wired through the server-side payment endpoint. This MVP uses a safe demo intent until a production provider key is configured.</p></div></div></section><Button type="submit" disabled={order.isPending || payment.isPending} className="h-12 rounded-full bg-[#20241f] px-7 font-bold hover:bg-[#e35f36]">{!isAuthenticated ? "Sign in to place order" : order.isPending ? "Preparing your order..." : "Place order"} <ArrowRight size={16} /></Button></form></div><aside className="h-fit rounded-[1.75rem] bg-[#20241f] p-7 text-[#f6f3ee] lg:sticky lg:top-28"><p className="text-xs font-bold uppercase tracking-[0.2em] text-[#d9e7d2]">Your order</p><div className="mt-7 space-y-4">{items.map(item => <div key={item.id} className="flex justify-between gap-4 text-sm"><span className="text-white/65">{item.name} × {item.quantity}</span><span>${(Number(item.price) * item.quantity).toFixed(2)}</span></div>)}<div className="border-t border-white/15 pt-4 text-sm"><div className="flex justify-between text-white/65"><span>Subtotal</span><span>${total.toFixed(2)}</span></div><div className="mt-3 flex justify-between text-white/65"><span>Shipping</span><span>{total >= 75 ? "Free" : "$6.00"}</span></div><div className="mt-4 flex justify-between text-base font-bold"><span>Total</span><span>${grandTotal.toFixed(2)}</span></div></div></div></aside></div></div>;
}
