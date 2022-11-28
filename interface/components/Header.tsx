// --- React methods
import React from "react";

// --- Components
import { ConnectButton } from "@rainbow-me/rainbowkit";

// --- Types
import { AuthenticationStatus } from "@rainbow-me/rainbowkit";

type HeaderProps = {
  authenticationStatus?: AuthenticationStatus;
}

const Header = ({ authenticationStatus }: HeaderProps): JSX.Element => {

  return (
    <div className="flex flex-row border-b-2 md:flex-row flex-wrap px-5 items-center w-full">
      {/* Left side row */}
      <div className="flex flex-col flex-wrap p-5">
        <div className="h-9 mb-4 flex flex-row items-center font-medium text-gray-900 md:mb-0">
          <img src="/assets/gitcoinLogoDark.svg" alt="Gitcoin Logo" />
          <img className="ml-6 mr-6" src="/assets/logoLine.svg" alt="Logo Line" />
          <img src="/assets/passportLogoBlack.svg" alt="Passport Logo" />
        </div>
      </div>
      {/* Right side row  */}
      <div className="flex flex-col w-[10rem] md:w-[30rem] lg:w-[72rem]">
        <div className="flex flex-row items-center justify-end">
          {
            authenticationStatus === "authenticated"
            ? <ConnectButton showBalance={false} />
            : <div></div>
          }
        </div>
      </div>
    </div>
  );
};

export default Header;
