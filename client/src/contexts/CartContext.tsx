import { createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren } from "react";

export type CartProduct = {
  id: number;
  vendorId: number;
  name: string;
  price: number | string;
  imageUrl?: string | null;
  category?: string;
};

type CartItem = CartProduct & { quantity: number };

type CartContextValue = {
  items: CartItem[];
  count: number;
  total: number;
  add: (product: CartProduct) => void;
  remove: (productId: number) => void;
  setQuantity: (productId: number, quantity: number) => void;
  clear: () => void;
};

const CartContext = createContext<CartContextValue | null>(null);
const STORAGE_KEY = "rijoya-cart";

export function CartProvider({ children }: PropsWithChildren) {
  const [items, setItems] = useState<CartItem[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]") as CartItem[];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  }, [items]);

  const value = useMemo<CartContextValue>(() => ({
    items,
    count: items.reduce((sum, item) => sum + item.quantity, 0),
    total: items.reduce((sum, item) => sum + Number(item.price) * item.quantity, 0),
    add: product => setItems(current => {
      const found = current.find(item => item.id === product.id);
      if (found) return current.map(item => item.id === product.id ? { ...item, quantity: item.quantity + 1 } : item);
      return [...current, { ...product, quantity: 1 }];
    }),
    remove: productId => setItems(current => current.filter(item => item.id !== productId)),
    setQuantity: (productId, quantity) => setItems(current => current.map(item => item.id === productId ? { ...item, quantity: Math.max(1, quantity) } : item)),
    clear: () => setItems([]),
  }), [items]);

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const context = useContext(CartContext);
  if (!context) throw new Error("useCart must be used inside CartProvider");
  return context;
}
