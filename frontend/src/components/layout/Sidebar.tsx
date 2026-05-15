import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Sparkles,
  BrainCircuit,
  TrendingUp,
  Cable,
  SlidersHorizontal,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";

const NAV_ITEMS = [
  { to: "/dashboard",  label: "Dashboard",  icon: LayoutDashboard },
  { to: "/chat",       label: "Chat",        icon: Sparkles        },
  { to: "/agents",     label: "Agents",      icon: BrainCircuit    },
  { to: "/metrics",    label: "Metrics",     icon: TrendingUp      },
  { to: "/connectors", label: "Connectors",  icon: Cable           },
] as const;

const navClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "flex items-center gap-3 rounded-md px-3 py-2 text-[13px] font-medium transition-colors select-none",
    isActive
      ? "bg-accent text-foreground"
      : "text-muted-foreground hover:bg-accent hover:text-foreground",
  );

interface SidebarProps {
  onNavigate?: () => void;
}

export function Sidebar({ onNavigate }: SidebarProps) {
  return (
    <aside className="flex h-screen w-56 flex-col border-r border-border bg-secondary">

      {/* Brand */}
      <div className="flex h-[56px] items-center gap-2.5 px-4 shrink-0">
        <div className="flex h-[28px] w-[28px] items-center justify-center rounded-md bg-primary">
          <Zap className="h-3.5 w-3.5 text-primary-foreground" strokeWidth={2.5} />
        </div>
        <span className="text-sm font-semibold tracking-tight text-foreground">
          D2C AI
        </span>
      </div>

      {/* Primary nav — shifted down with proper breathing room */}
      <nav
        className="flex-1 flex flex-col gap-1 px-2 pt-5 pb-2 overflow-y-auto"
        aria-label="Main navigation"
      >
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} onClick={onNavigate} className={navClass}>
            <Icon className="h-[17px] w-[17px] shrink-0" aria-hidden />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Settings pinned at bottom */}
      <div className="px-2 pb-4 shrink-0">
        <NavLink to="/settings" onClick={onNavigate} className={navClass}>
          <SlidersHorizontal className="h-[17px] w-[17px] shrink-0" aria-hidden />
          Settings
        </NavLink>
      </div>

    </aside>
  );
}
