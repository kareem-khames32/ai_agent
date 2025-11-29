"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { X, CheckCircle, XCircle, AlertCircle, Info } from "lucide-react";

export type ToastType = "success" | "error" | "warning" | "info";

export interface Toast {
  id: string;
  type: ToastType;
  title: string;
  description?: string;
  duration?: number;
}

interface ToastContextValue {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, "id">) => void;
  removeToast: (id: string) => void;
}

const ToastContext = React.createContext<ToastContextValue | undefined>(undefined);

export function useToast() {
  const context = React.useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}

interface ToastProviderProps {
  children: React.ReactNode;
}

export function ToastProvider({ children }: ToastProviderProps) {
  const [toasts, setToasts] = React.useState<Toast[]>([]);

  const addToast = React.useCallback((toast: Omit<Toast, "id">) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { ...toast, id }]);

    // Auto remove after duration
    const duration = toast.duration || 5000;
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, duration);
  }, []);

  const removeToast = React.useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <ToastContainer />
    </ToastContext.Provider>
  );
}

function ToastContainer() {
  const { toasts, removeToast } = useToast();

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onClose={() => removeToast(toast.id)} />
      ))}
    </div>
  );
}

interface ToastItemProps {
  toast: Toast;
  onClose: () => void;
}

function ToastItem({ toast, onClose }: ToastItemProps) {
  const icons = {
    success: <CheckCircle className="h-5 w-5 text-[var(--success)]" />,
    error: <XCircle className="h-5 w-5 text-[var(--error)]" />,
    warning: <AlertCircle className="h-5 w-5 text-[var(--warning)]" />,
    info: <Info className="h-5 w-5 text-[var(--info)]" />,
  };

  const borderColors = {
    success: "border-l-[var(--success)]",
    error: "border-l-[var(--error)]",
    warning: "border-l-[var(--warning)]",
    info: "border-l-[var(--info)]",
  };

  return (
    <div
      className={cn(
        "flex w-[360px] items-start gap-3 rounded-lg border border-[var(--border)] border-l-4 bg-[var(--card)] p-4 shadow-lg animate-slide-in",
        borderColors[toast.type]
      )}
    >
      {icons[toast.type]}
      <div className="flex-1">
        <p className="font-medium text-[var(--foreground)]">{toast.title}</p>
        {toast.description && (
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            {toast.description}
          </p>
        )}
      </div>
      <button
        onClick={onClose}
        className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

// Helper functions for easy usage
export function toast(toastData: Omit<Toast, "id">) {
  // This will be used with the context
  return toastData;
}
