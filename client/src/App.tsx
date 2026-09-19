import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { MarketplaceShell } from "@/components/MarketplaceShell";
import { CartProvider } from "@/contexts/CartContext";
import AdminDashboard from "@/pages/AdminDashboard";
import Cart from "@/pages/Cart";
import Catalog from "@/pages/Catalog";
import Checkout from "@/pages/Checkout";
import Home from "@/pages/Home";
import NotFound from "@/pages/NotFound";
import VendorDashboard from "@/pages/VendorDashboard";
import VendorRegistration from "@/pages/VendorRegistration";
import { Route, Switch } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./contexts/ThemeContext";

function PublicRoutes() {
  return <MarketplaceShell><Switch><Route path="/" component={Home} /><Route path="/catalog" component={Catalog} /><Route path="/vendor/register" component={VendorRegistration} /><Route path="/cart" component={Cart} /><Route path="/checkout" component={Checkout} /><Route path="/404" component={NotFound} /><Route component={NotFound} /></Switch></MarketplaceShell>;
}

function App() {
  return <ErrorBoundary><ThemeProvider defaultTheme="light"><TooltipProvider><Toaster /><CartProvider><Switch><Route path="/vendor/dashboard" component={VendorDashboard} /><Route path="/admin" component={AdminDashboard} /><Route component={PublicRoutes} /></Switch></CartProvider></TooltipProvider></ThemeProvider></ErrorBoundary>;
}

export default App;
