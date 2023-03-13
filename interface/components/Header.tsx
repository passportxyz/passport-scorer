// --- React methods
import { useRouter } from "next/router";
import React, { useContext, useEffect, useMemo, useRef } from "react";
import { UserContext } from "../context/userContext";
import { UIMode } from "../utils/dark-mode";
// import { initOnboard } from "../utils/onboard";

type HeaderProps = {
  mode?: UIMode;
  className?: string;
  accountCenterContainerRef?: React.RefObject<HTMLDivElement>;
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

const ONBOARD_DIV_ID = "account-center-container";

const Header = ({
  mode,
  className,
  accountCenterContainer,
}: HeaderProps): JSX.Element => {
  const assets = useMemo(() => getAssets(mode), [mode]);
  const router = useRouter();

  const { connected } = useContext(UserContext);

  useEffect(() => {
    if (!connected) {
      router.push("/");
    }
  }, [connected]);

  return (
    <div className={`flex items-center justify-between pt-7 ${className}`}>
      <>
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
      </>
    </div>
  );
};

export default Header;
