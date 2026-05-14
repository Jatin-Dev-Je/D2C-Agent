import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  MessageSquare,
  Bot,
  BarChart3,
  Plug,
  Settings,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { useSessionStore } from "@/stores/session";
import { Separator } from "@/components/ui/separator";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/agents", label: "Agents", icon: Bot },
  { to: "/metrics", label: "Metrics", icon: BarChart3 },
  { to: "/connectors", label: "Connectors", icon: Plug },
] as const;

interface SidebarProps {
  onNavigate?: () => void;
}

export function Sidebar({ onNavigate }: SidebarProps) {
  const { claims, isAuthenticated } = useSessionStore();

  return (
    <aside className="flex h-screen w-56 flex-col border-r border-border bg-card">
      {/* Logo */}
      <div className="flex h-14 items-center gap-2.5 px-4 border-b border-border shrink-0">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary">
          <Zap className="h-4 w-4 text-primary-foreground" />
        </div>
        <span className="text-sm font-semibold tracking-tight">D2C AI</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-0.5 px-2 py-3 overflow-y-auto" aria-label="Main navigation">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" aria-hidden />
            {label}
          </NavLink>
        ))}
      </nav>

      <Separator />

      {/* Bottom: Settings + Merchant info */}
      <div className="space-y-0.5 px-2 py-3 shrink-0">
        <NavLink
          to="/settings"
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
              isActive
                ? "bg-primary/10 text-primary font-medium"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )
          }
        >
          <Settings className="h-4 w-4 shrink-0" aria-hidden />
          Settings
        </NavLink>

        {isAuthenticated && claims && (
          <div className="px-3 py-2 space-y-0.5">
            <p className="text-xs text-muted-foreground truncate">{claims.email}</p>
            <p className="text-xs text-muted-foreground/50 truncate font-mono">
              {claims.merchant_id.slice(0, 12)}…
            </p>
          </div>
        )}
      </div>
    </aside>
  );
}
