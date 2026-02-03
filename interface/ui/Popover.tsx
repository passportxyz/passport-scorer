import React, { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { cn } from "../utils/cn";
import { XMarkIcon } from "@heroicons/react/24/outline";

export interface PopoverProps {
  trigger: React.ReactNode;
  children: React.ReactNode;
  placement?: "top" | "bottom" | "left" | "right";
  className?: string;
}

export function Popover({
  trigger,
  children,
  placement = "top",
  className,
}: PopoverProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLSpanElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  const updatePosition = useCallback(() => {
    if (triggerRef.current && popoverRef.current) {
      const triggerRect = triggerRef.current.getBoundingClientRect();
      const popoverRect = popoverRef.current.getBoundingClientRect();

      let top = 0;
      let left = 0;

      switch (placement) {
        case "top":
          top = triggerRect.top - popoverRect.height - 8;
          left = triggerRect.left + triggerRect.width / 2 - popoverRect.width / 2;
          break;
        case "bottom":
          top = triggerRect.bottom + 8;
          left = triggerRect.left + triggerRect.width / 2 - popoverRect.width / 2;
          break;
        case "left":
          top = triggerRect.top + triggerRect.height / 2 - popoverRect.height / 2;
          left = triggerRect.left - popoverRect.width - 8;
          break;
        case "right":
          top = triggerRect.top + triggerRect.height / 2 - popoverRect.height / 2;
          left = triggerRect.right + 8;
          break;
      }

      // Keep popover within viewport
      left = Math.max(8, Math.min(left, window.innerWidth - popoverRect.width - 8));
      top = Math.max(8, Math.min(top, window.innerHeight - popoverRect.height - 8));

      setPosition({ top, left });
    }
  }, [placement]);

  const handleClickOutside = useCallback(
    (e: MouseEvent) => {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(e.target as Node) &&
        triggerRef.current &&
        !triggerRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    },
    []
  );

  useEffect(() => {
    if (isOpen) {
      // Use requestAnimationFrame to ensure popover is rendered before measuring
      requestAnimationFrame(updatePosition);
      document.addEventListener("mousedown", handleClickOutside);
      window.addEventListener("scroll", updatePosition, true);
      window.addEventListener("resize", updatePosition);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      window.removeEventListener("scroll", updatePosition, true);
      window.removeEventListener("resize", updatePosition);
    };
  }, [isOpen, handleClickOutside, updatePosition]);

  const popover = isOpen && typeof document !== "undefined" && (
    createPortal(
      <div
        ref={popoverRef}
        className={cn(
          "fixed z-50 rounded-md bg-foreground px-4 py-3 text-sm text-background shadow-lg",
          className
        )}
        style={{
          top: position.top,
          left: position.left,
        }}
      >
        <button
          onClick={() => setIsOpen(false)}
          className="absolute right-2 top-2 rounded-full p-0.5 text-background/70 hover:text-background transition-colors"
          aria-label="Close popover"
        >
          <XMarkIcon className="h-4 w-4" />
        </button>
        <div className="pr-4">{children}</div>
        {/* Arrow */}
        <div
          className={cn(
            "absolute h-2 w-2 rotate-45 bg-foreground",
            placement === "top" && "bottom-[-4px] left-1/2 -translate-x-1/2",
            placement === "bottom" && "top-[-4px] left-1/2 -translate-x-1/2",
            placement === "left" && "right-[-4px] top-1/2 -translate-y-1/2",
            placement === "right" && "left-[-4px] top-1/2 -translate-y-1/2"
          )}
        />
      </div>,
      document.body
    )
  );

  return (
    <>
      <span
        ref={triggerRef}
        onClick={() => setIsOpen(!isOpen)}
        className="cursor-pointer"
      >
        {trigger}
      </span>
      {popover}
    </>
  );
}
