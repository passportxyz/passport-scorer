import React, { useMemo } from "react";
import { UIMode } from "../utils/dark-mode";

const getAssets = (mode?: UIMode) => {
  const darkMode = mode === "dark";
  return {
    emphasisColor: darkMode ? "white" : "black",
    docsIcon: darkMode
      ? "/assets/docsIconLight.svg"
      : "/assets/docsIconDark.svg",
    githubLogo: darkMode
      ? "/assets/githubLogoLight.svg"
      : "/assets/githubLogoDark.svg",
  };
};

type FooterProps = {
  mode?: UIMode;
  className?: string;
};

const Footer = ({ mode, className }: FooterProps): JSX.Element => {
  const assets = useMemo(() => getAssets(mode), [mode]);

  return (
    <div
      className={`flex h-[120px] items-center justify-between text-base ${className}`}
    >
      <div className="">
        Available on
        <a
          href="https://ceramic.network/"
          target="_blank"
          rel="noopener noreferrer"
          className={`text-${assets.emphasisColor} ml-1 hover:underline`}
        >
          Ceramic.
        </a>
      </div>
      <div className="flex">
        <a
          href="https://github.com/gitcoinco/passport"
          target="_blank"
          rel="noopener noreferrer"
          className="mr-6"
        >
          <img src={assets.githubLogo} alt="Github Logo" />
        </a>
        <a
          href="https://docs.passport.gitcoin.co/building-with-passport/quick-start-guide"
          target="_blank"
          rel="noopener noreferrer"
          className=""
        >
          <img src={assets.docsIcon} alt="Docs Icon" />
        </a>
      </div>
    </div>
  );
};

export default Footer;
