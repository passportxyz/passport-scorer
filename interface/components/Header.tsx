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
    <div className="flex flex-row border-gray-lightgray border-b-2 flex-wrap px-5 items-center w-full">
      {/* Left side row */}
      <div className="flex flex-col flex-wrap py-2 sm:p-5">
        <div className="h-9 mb-0 flex flex-row items-center font-medium text-gray-900">
          <img className="w-5 sm:w-full" src="/assets/gitcoinLogoDark.svg" alt="Gitcoin Logo" />
          <img className="md:mx-6 mx-3" src="/assets/logoLine.svg" alt="Logo Line" />
          <img className="w-3/6 sm:w-full" src="/assets/passportLogoBlack.svg" alt="Passport Logo" />
        </div>
      </div>
      {/* Right side row  */}
      <div className="flex flex-col ml-auto py-2 sm:py-0 items-center pr-1 sm:pr-5">
        <div className="flex flex-row items-center justify-end">
          {
            authenticationStatus === "authenticated"
            ? <ConnectButton showBalance={false} accountStatus={{ smallScreen: "avatar", largeScreen: "full" }} />
            : <div></div>
          }
        </div>
      </div>
    </div>
  );
};

export default Header;
