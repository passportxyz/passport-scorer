// --- React methods
import React, { useMemo } from "react";
import { UIMode } from "../utils/dark-mode";

type MinimalHeaderProps = {
  mode?: UIMode;
  className?: string;
};

const getAssets = (mode?: UIMode) => {
  // Always use dark logos for light theme
  return {
    gitcoinLogo: "/assets/gitcoinLogoDark.svg",
    scorerWord: "/assets/scorerWordBlack.svg",
    logoLine: "/assets/logoLine.svg",
    emphasisColor: "black",
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
        <img className="" src={assets.gitcoinLogo} alt="Human Logo" />
        <img className="mx-3 md:mx-6" src={assets.logoLine} alt="Logo Line" />
        <Logo />
        <img
          className="mx-3 hidden md:block"
          src={assets.scorerWord}
          alt="Scorer"
        />
      </div>
    </div>
  );
};

export default MinimalHeader;
