"use client";

import { DashboardLayout } from "@/components/layout";
import { ToastProvider } from "@/components/ui/toast";

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <ToastProvider>
      <DashboardLayout>{children}</DashboardLayout>
    </ToastProvider>
  );
}
