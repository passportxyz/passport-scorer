import React, { useMemo } from "react";
import { UIMode } from "../utils/dark-mode";
import { PAGE_PADDING } from "./PageLayout";

const getAssets = (mode?: UIMode) => {
  const darkMode = mode === "dark";
  return {
    emphasisColor: darkMode ? "white" : "purple-darkpurple",
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
  hideLinks?: boolean;
};

const Footer = ({ mode, className, hideLinks }: FooterProps): JSX.Element => {
  const assets = useMemo(() => getAssets(mode), [mode]);

  return (
    <div
      className={`flex h-[120px] items-center justify-between text-base ${PAGE_PADDING} ${className}`}
    >
      <div className="text-purple-softpurple">
        {/* Just a placeholder */}
      </div>
      <div className={`flex ${hideLinks ? "hidden" : ""}`}>
        <a
          href={`https://github.com/gitcoinco/passport-scorer/commit/${process.env.NEXT_PUBLIC_GIT_COMMIT_HASH}`}
          target="_blank"
          rel="noopener noreferrer"
          className="mr-8 text-purple-darkpurple"
        >
          Git commit
        </a>
        <a
          href="https://github.com/gitcoinco/passport"
          target="_blank"
          rel="noopener noreferrer"
          className="mr-8"
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
