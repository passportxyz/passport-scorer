// --- React methods
import React from "react";

const Header = ({}): JSX.Element => {
  return (
    <div className="flex flex-row border-b-2 md:flex-row flex-wrap w-full px-5">
      <div className="flex flex-col flex-wrap p-5">
        <div className="float-right h-9 mb-4 flex flex-row items-center font-medium text-gray-900 md:mb-0">
          <img src="/assets/gitcoinLogoDark.svg" alt="Gitcoin Logo" />
          <img className="ml-6 mr-6" src="/assets/logoLine.svg" alt="Logo Line" />
          <img src="/assets/passportLogoBlack.svg" alt="Passport Logo" />
        </div>
      </div>
      <div className="flex flex-row flex-wrap p-5 mx-auto justify-end">
        <div className="mb-4 flex h-12 font-medium text-gray-900 md:mb-0 items-center">
          <p className="flex font-light">Ceramic status</p>
        </div>
      </div>
    </div>
  );
};

export default Header;
