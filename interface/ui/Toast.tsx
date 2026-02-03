import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import { createPortal } from "react-dom";
import { cn } from "../utils/cn";
import { CheckCircleIcon, XMarkIcon, ExclamationCircleIcon } from "@heroicons/react/24/outline";

export type ToastType = "success" | "error" | "warning" | "info";

export interface Toast {
  id: string;
  message: string;
  type: ToastType;
  duration?: number;
}

interface ToastContextValue {
  toasts: Toast[];
  addToast: (message: string, type?: ToastType, duration?: number) => void;
  removeToast: (id: string) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  warning: (message: string) => void;
  closeAll: () => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const addToast = useCallback(
    (message: string, type: ToastType = "info", duration: number = 6000) => {
      const id = Math.random().toString(36).substr(2, 9);
      const toast: Toast = { id, message, type, duration };
      setToasts((prev) => [...prev, toast]);

      if (duration > 0) {
        setTimeout(() => removeToast(id), duration);
      }
    },
    [removeToast]
  );

  const success = useCallback(
    (message: string) => addToast(message, "success"),
    [addToast]
  );

  const error = useCallback(
    (message: string) => addToast(message, "error"),
    [addToast]
  );

  const warning = useCallback(
    (message: string) => addToast(message, "warning"),
    [addToast]
  );

  const closeAll = useCallback(() => {
    setToasts([]);
  }, []);

  return (
    <ToastContext.Provider
      value={{ toasts, addToast, removeToast, success, error, warning, closeAll }}
    >
      {children}
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}

interface ToastContainerProps {
  toasts: Toast[];
  onRemove: (id: string) => void;
}

function ToastContainer({ toasts, onRemove }: ToastContainerProps) {
  if (typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed bottom-20 left-1/2 z-50 flex -translate-x-1/2 flex-col gap-2">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onRemove={onRemove} />
      ))}
    </div>,
    document.body
  );
}

interface ToastItemProps {
  toast: Toast;
  onRemove: (id: string) => void;
}

function ToastItem({ toast, onRemove }: ToastItemProps) {
  const icons = {
    success: <CheckCircleIcon className="h-6 w-6 text-emerald-500" />,
    error: <ExclamationCircleIcon className="h-6 w-6 text-red-500" />,
    warning: <ExclamationCircleIcon className="h-6 w-6 text-amber-500" />,
    info: <CheckCircleIcon className="h-6 w-6 text-gray-600" />,
  };

  const bgColors = {
    success: "bg-gray-900",
    error: "bg-gray-900",
    warning: "bg-amber-50",
    info: "bg-gray-900",
  };

  const textColors = {
    success: "text-white",
    error: "text-white",
    warning: "text-gray-900",
    info: "text-white",
  };

  return (
    <div
      className={cn(
        "flex items-center gap-4 rounded-[12px] px-4 py-4 shadow-card",
        bgColors[toast.type]
      )}
    >
      {icons[toast.type]}
      <span className={cn("text-base", textColors[toast.type])}>
        {toast.message}
      </span>
      <button
        onClick={() => onRemove(toast.id)}
        className={cn(
          "ml-4 cursor-pointer hover:opacity-70 transition-opacity",
          textColors[toast.type]
        )}
      >
        <XMarkIcon className="h-4 w-4" />
      </button>
    </div>
  );
}
