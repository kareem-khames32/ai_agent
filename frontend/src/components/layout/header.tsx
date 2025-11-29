"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Avatar } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Search,
  Bell,
  ChevronDown,
  User,
  Settings,
  LogOut,
  HelpCircle,
} from "lucide-react";

interface HeaderProps {
  sidebarCollapsed: boolean;
}

const pageTitles: Record<string, string> = {
  "/overview": "Overview",
  "/assistants": "Assistants",
  "/tools": "Tools",
  "/phone-numbers": "Phone Numbers",
  "/voice-library": "Voice Library",
  "/squads": "Squads",
  "/call-logs": "Call Logs",
  "/metrics": "Metrics",
  "/api-keys": "API Keys",
  "/settings": "Settings",
};

export function Header({ sidebarCollapsed }: HeaderProps) {
  const pathname = usePathname();

  // Get page title from pathname
  const getPageTitle = () => {
    // Check exact match first
    if (pageTitles[pathname]) {
      return pageTitles[pathname];
    }
    // Check for nested routes
    const basePath = "/" + pathname.split("/")[1];
    return pageTitles[basePath] || "Dashboard";
  };

  return (
    <header
      className={cn(
        "fixed top-0 right-0 z-30 flex h-16 items-center justify-between border-b border-[var(--border)] bg-[var(--background)] px-6 transition-all duration-300",
        sidebarCollapsed ? "left-16" : "left-60"
      )}
    >
      {/* Left side - Page title and search */}
      <div className="flex items-center gap-6">
        <h1 className="text-xl font-semibold text-[var(--foreground)]">
          {getPageTitle()}
        </h1>
        <div className="hidden md:block">
          <Input
            placeholder="Search..."
            className="w-64"
            leftIcon={<Search className="h-4 w-4" />}
          />
        </div>
      </div>

      {/* Right side - Actions */}
      <div className="flex items-center gap-4">
        {/* Notifications */}
        <button className="relative flex h-9 w-9 items-center justify-center rounded-lg hover:bg-[var(--secondary)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
          <Bell className="h-5 w-5" />
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-[var(--primary)]" />
        </button>

        {/* Help */}
        <button className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-[var(--secondary)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
          <HelpCircle className="h-5 w-5" />
        </button>

        {/* User Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-2 rounded-lg px-2 py-1 hover:bg-[var(--secondary)]">
              <Avatar size="sm" fallback="U" />
              <span className="hidden text-sm font-medium text-[var(--foreground)] md:block">
                User
              </span>
              <ChevronDown className="h-4 w-4 text-[var(--muted-foreground)]" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>My Account</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem>
              <User className="mr-2 h-4 w-4" />
              Profile
            </DropdownMenuItem>
            <DropdownMenuItem>
              <Settings className="mr-2 h-4 w-4" />
              Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem destructive>
              <LogOut className="mr-2 h-4 w-4" />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
