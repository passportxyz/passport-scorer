// --- React Methods
import React, { useState, useRef } from "react";

// --- Wagmi
import { useAccount, useConnect } from "wagmi";

// --- Components
import Header from "../components/Header";
import Footer from "../components/Footer";
import { ConnectButton } from "@rainbow-me/rainbowkit";

export default function Home() {
  return (
    <div className="font-libre-franklin flex h-full min-h-default flex-col justify-between bg-purple-darkpurple px-4 text-gray-400 sm:px-20">
      <Header mode="dark" />
      <div className="container pb-10">
        <div className="flex flex-wrap">
          <div className="pb-6 sm:w-2/3 xl:w-1/2">
            <div className="font-miriam-libre leading-relaxed text-white">
              <img
                src="/assets/gitcoinWordLogo.svg"
                alt="Gitcoin Logo"
                className="py-4"
              />
              <p className="-ml-1 text-5xl sm:text-7xl">Passport Scorer</p>
            </div>
            <div className="py-6">
              We all know that Sybil attackers want to sabotage your
              project&apos;s future, but stopping them is really hard and
              expensive if you want to do it on your own. Gitcoin Passport is a
              free, open source tool that gives you Gitcoin-grade Sybil
              protection with only a few lines of code, so you can focus your
              time, money, and attention on growing your business.
            </div>
            {/* TODO this can be simpler, this is just temporary as we switch wallet connectors */}
            {/* TODO once ready to switch just pull out the button component and change onClick */}
            <ConnectButton.Custom>
              {({ openConnectModal }) => {
                return (
                  <button
                    data-testid="connectWalletButton"
                    className="rounded bg-purple-gitcoinpurple px-8 py-3 text-lg text-white"
                    onClick={openConnectModal}
                  >
                    <img
                      src="/assets/ethLogo.svg"
                      alt="Ethereum Logo"
                      className="mr-3 inline h-auto w-4"
                    />
                    <span className="inline">Sign-in with Ethereum</span>
                  </button>
                );
              }}
            </ConnectButton.Custom>
          </div>
        </div>
      </div>
      <Footer mode="dark" />
    </div>
  );
}
