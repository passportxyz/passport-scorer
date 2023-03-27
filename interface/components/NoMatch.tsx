// --- React Methods
import React, { useMemo } from "react";

// --- React Router Methods
import { useNavigate } from "react-router-dom";

import { PrimaryBtn } from "./PrimrayBtn";
import {
  HeaderContentFooterGrid,
  PAGE_PADDING,
  GlobalLayout,
} from "../components/PageLayout";
import Header from "./Header";
import Footer from "./Footer";

const NoMatch = () => {
  const navigate = useNavigate();
  const navigateToHome = () => {
    navigate("/");
  };

  return (
    <GlobalLayout>
      <div className="bg-gray-bluegray">
        <HeaderContentFooterGrid>
          <div className={"border-b border-gray-300 bg-white"}>
            <div className={`w-full bg-white ${PAGE_PADDING}`}>
              <Header />
            </div>
          </div>
          <div className="mx-8 mt-16 flex flex-col items-center">
            <div className="text-sm text-purple-gitcoinpurple">
              405 - Page Not Found
            </div>
            <h2 className="text-2xl text-purple-darkpurple">
              Uh oh! You might be a little lost.
            </h2>
            <div className="text-xs text-purple-softpurple">
              It looks like the page you&apos;re looking for doesn&apos;t exist.
              For support, contact us on{" "}
              <a href="" className="text-purple-gitcoinpurple">
                Discord
              </a>
              .
            </div>
            <button
              className="mb-8 mt-8 rounded bg-purple-gitcoinpurple p-4 py-3 text-white"
              onClick={navigateToHome}
            >
              Go back home
            </button>
            <img src="/assets/404.svg" />
          </div>
          <Footer className={PAGE_PADDING} />
        </HeaderContentFooterGrid>
      </div>
    </GlobalLayout>
  );
};

export default NoMatch;
