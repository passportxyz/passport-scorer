// --- React methods
import React, { useMemo } from "react";
import { UIMode } from "../utils/dark-mode";

type MinimalHeaderProps = {
  mode?: UIMode;
  className?: string;
};

const Logo = () => (
  <div className="relative w-9">
    <img
      className="absolute -top-[.8rem] left-0 max-w-none"
      src="/assets/logo1.svg"
    />
    <img
      className="absolute -top-[.8rem] left-1 max-w-none"
      src="/assets/logo2.svg"
    />
    <img
      className="absolute -top-2 left-2 max-w-none"
      src="/assets/logo3.svg"
    />
  </div>
);

const MinimalHeader = ({
  mode,
  className,
}: MinimalHeaderProps): JSX.Element => {
  const headerTextColor =
    mode === "dark" ? "font-bold text-white" : "font-bold text-black";

  return (
    <div className={`flex h-16 ${className}`}>
      <div className="flex items-center">
        <Logo />
        <span className={headerTextColor}>Developer Portal</span>
      </div>
    </div>
  );
};

export default MinimalHeader;
