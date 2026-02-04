"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Bot,
  Wrench,
  Phone,
  Mic,
  Users,
  PhoneCall,
  BarChart3,
  Settings,
  Key,
  ChevronLeft,
  ChevronRight,
  Zap,
  Radio,
  Workflow,
} from "lucide-react";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

const navigation = [
  { name: "Overview", href: "/overview", icon: LayoutDashboard },
  // Pipeline Section
  { name: "Pipeline Assistants", href: "/pipeline-assistants", icon: Workflow },
  { name: "Pipeline Call", href: "/pipeline-call", icon: PhoneCall },
  // Realtime Section
  { name: "Realtime Assistants", href: "/realtime-assistants", icon: Zap },
  { name: "Realtime Call", href: "/realtime-call", icon: Radio },
  // Other
  { name: "Tools", href: "/tools", icon: Wrench },
  { name: "Phone Numbers", href: "/phone-numbers", icon: Phone },
  { name: "Voice Library", href: "/voice-library", icon: Mic },
  { name: "Call Logs", href: "/call-logs", icon: PhoneCall },
  { name: "Metrics", href: "/metrics", icon: BarChart3 },
];

const bottomNavigation = [
  { name: "API Keys", href: "/api-keys", icon: Key },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-[var(--border)] bg-[var(--card)] transition-all duration-300",
        collapsed ? "w-16" : "w-60"
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center justify-between border-b border-[var(--border)] px-4">
        <Link href="/overview" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--primary)]">
            <Zap className="h-5 w-5 text-[var(--primary-foreground)]" />
          </div>
          {!collapsed && (
            <span className="text-lg font-bold text-[var(--foreground)]">
              VoiceAI
            </span>
          )}
        </Link>
        <button
          onClick={onToggle}
          className="flex h-6 w-6 items-center justify-center rounded-md hover:bg-[var(--secondary)] text-[var(--muted-foreground)]"
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* Main Navigation */}
      <nav className="flex-1 space-y-1 px-2 py-4">
        {navigation.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--foreground)]",
                collapsed && "justify-center px-2"
              )}
              title={collapsed ? item.name : undefined}
            >
              <item.icon className="h-5 w-5 shrink-0" />
              {!collapsed && <span>{item.name}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Bottom Navigation */}
      <div className="border-t border-[var(--border)] px-2 py-4 space-y-1">
        {bottomNavigation.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--foreground)]",
                collapsed && "justify-center px-2"
              )}
              title={collapsed ? item.name : undefined}
            >
              <item.icon className="h-5 w-5 shrink-0" />
              {!collapsed && <span>{item.name}</span>}
            </Link>
          );
        })}
      </div>
    </aside>
  );
}
