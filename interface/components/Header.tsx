// --- React methods
import React, { useCallback, useMemo } from "react";
import { UIMode } from "../utils/dark-mode";

// --- Components
import { ConnectButton } from "@rainbow-me/rainbowkit";

// --- Types
import { AuthenticationStatus } from "@rainbow-me/rainbowkit";

type HeaderProps = {
  authenticationStatus?: AuthenticationStatus;
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

const Header = ({
  authenticationStatus,
  mode,
  className,
}: HeaderProps): JSX.Element => {
  const assets = useMemo(() => getAssets(mode), [mode]);

  return (
    <div className={`flex items-center justify-between pt-3 ${className}`}>
      {/* Left side row */}
      <div className="flex items-center">
        <img className="" src={assets.gitcoinLogo} alt="Gitcoin Logo" />
        <img className="mx-3 md:mx-6" src={assets.logoLine} alt="Logo Line" />
        <Logo />
        <img
          className="mx-3 hidden sm:block"
          src={assets.scorerWord}
          alt="Scorer"
        />
      </div>
      {/* Right side row  */}
      <div>
        {authenticationStatus === "authenticated" && (
          <ConnectButton
            showBalance={false}
            accountStatus={{ smallScreen: "avatar", largeScreen: "full" }}
          />
        )}
      </div>
    </div>
  );
};

export default Header;
