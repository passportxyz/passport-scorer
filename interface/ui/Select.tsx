import React, { SelectHTMLAttributes, forwardRef } from "react";
import { cn } from "../utils/cn";

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "children"> {
  label?: string;
  options?: SelectOption[];
  error?: string;
  children?: React.ReactNode;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, options, error, className, children, ...props }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label className="mb-2 block text-xs font-medium text-gray-900">
            {label}
          </label>
        )}
        <select
          ref={ref}
          className={cn(
            "w-full rounded-[12px] border border-gray-200 bg-white px-4 py-3 text-base text-gray-900 cursor-pointer focus:border-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-200 transition-colors",
            error && "border-error focus:border-error focus:ring-error/50",
            className
          )}
          {...props}
        >
          {options
            ? options.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))
            : children}
        </select>
        {error && (
          <p className="mt-1 text-sm text-error">{error}</p>
        )}
      </div>
    );
  }
);

Select.displayName = "Select";
