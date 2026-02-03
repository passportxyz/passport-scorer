import React, { createContext, useContext } from "react";
import { cn } from "../utils/cn";

interface RadioGroupContextValue {
  value: string;
  onChange: (value: string) => void;
  name: string;
}

const RadioGroupContext = createContext<RadioGroupContextValue | undefined>(undefined);

export interface RadioGroupProps {
  value: string;
  onChange: (value: string) => void;
  name?: string;
  children: React.ReactNode;
  className?: string;
}

export function RadioGroup({
  value,
  onChange,
  name = "radio-group",
  children,
  className,
}: RadioGroupProps) {
  return (
    <RadioGroupContext.Provider value={{ value, onChange, name }}>
      <div className={cn("flex flex-col gap-2", className)} role="radiogroup">
        {children}
      </div>
    </RadioGroupContext.Provider>
  );
}

export interface RadioProps {
  value: string;
  children?: React.ReactNode;
  className?: string;
  disabled?: boolean;
  onChange?: () => void;
}

export function Radio({
  value,
  children,
  className,
  disabled,
  onChange: onChangeProp,
}: RadioProps) {
  const context = useContext(RadioGroupContext);

  if (!context) {
    throw new Error("Radio must be used within a RadioGroup");
  }

  const { value: groupValue, onChange, name } = context;
  const isChecked = groupValue === value;

  const handleChange = () => {
    if (!disabled) {
      onChange(value);
      onChangeProp?.();
    }
  };

  return (
    <label
      className={cn(
        "flex cursor-pointer items-start gap-3",
        disabled && "cursor-not-allowed opacity-50",
        className
      )}
    >
      <div className="relative mt-0.5 flex items-center justify-center">
        <input
          type="radio"
          name={name}
          value={value}
          checked={isChecked}
          onChange={handleChange}
          disabled={disabled}
          className="sr-only"
        />
        <div
          className={cn(
            "h-5 w-5 rounded-full border-2 transition-colors",
            isChecked
              ? "border-primary bg-primary"
              : "border-border bg-background hover:border-primary/50"
          )}
        >
          {isChecked && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="h-2 w-2 rounded-full bg-primary-foreground" />
            </div>
          )}
        </div>
      </div>
      {children && <div className="flex-1">{children}</div>}
    </label>
  );
}
