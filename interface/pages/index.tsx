// --- React Methods
import React from "react";

// --- Components
import Header from "../components/Header";
import Footer from "../components/Footer";
import { ConnectButton } from "@rainbow-me/rainbowkit";

export default function Home() {
  return (
    // When the user successfully connects their wallet, they're routed to the Dashboard
    <>
      <div>
        <Header />
      </div>
      <div className="container mx-auto px-5 py-2 h-full">
        <div className="mt-0 w-full pb-6 text-white sm:mt-40 sm:w-1/2 md:mt-40 md:w-1/2 md:pt-6">
          <div className="font-miriam-libre leading-relaxed">
            <img src="/assets/gitcoinWordLogo.svg" alt="Passport Logo" className="py-4 px-1" />
            <p className="text-5xl sm:text-7xl md:text-7xl text-gray-600">Passport</p>
          </div>
          <div className="font-libre-franklin mt-0 text-lg text-gray-400 sm:text-xl md:mt-10 md:pr-20 md:text-xl">
          Gitcoin Passport is an identity protocol that proves your trustworthiness without needing to collect personally identifiable information.
          </div>
          <div className="mt-4 w-full sm:mt-10 sm:w-1/2 md:mt-10 md:block md:w-1/2">
            <ConnectButton label="Connect Wallet" />
          </div>
        </div>
      </div>
      <div className="mt-12">
        <Footer />
      </div>
    </>
  );
};
