import React, { ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "../utils/cn";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-[12px] font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-gray-400",
          {
            "bg-black text-white hover:bg-gray-800 focus:ring-gray-500": variant === "primary",
            "border border-gray-200 bg-white text-gray-900 hover:bg-gray-50 focus:ring-gray-300": variant === "secondary",
            "bg-transparent text-gray-700 hover:bg-gray-100 focus:ring-gray-300": variant === "ghost",
            "bg-error text-white hover:bg-error/90 focus:ring-error": variant === "danger",
          },
          {
            "px-3 py-1.5 text-sm": size === "sm",
            "px-4 py-2 text-base": size === "md",
            "px-6 py-3 text-base": size === "lg",
          },
          className
        )}
        {...props}
      >
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
