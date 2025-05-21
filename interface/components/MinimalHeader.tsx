// --- React methods
import React, { useMemo } from "react";
import { UIMode } from "../utils/dark-mode";

type MinimalHeaderProps = {
  mode?: UIMode;
  className?: string;
};

const getAssets = (mode?: UIMode) => {
  const darkMode = mode === "dark";
  return {
    gitcoinLogo: darkMode
      ? "/assets/gitcoinLogoWhite.svg"
      : "/assets/gitcoinLogoDark.svg",
    scorerWord: darkMode
      ? "/assets/scorerWordWhite.svg"
      : "/assets/scorerWordBlack.svg",
    logoLine: "/assets/logoLine.svg",
    emphasisColor: darkMode ? "white" : "black",
  };
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
  const assets = useMemo(() => getAssets(mode), [mode]);

  return (
    <div className={`flex h-16 ${className}`}>
      <div className="flex items-center">
        <Logo />
        <span className="font-bold text-white">Developer Portal</span>
      </div>
    </div>
  );
};

export default MinimalHeader;
