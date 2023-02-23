// --- React Methods
import React, { useState, useRef, useContext } from "react";

// --- Components
import Header from "../components/Header";
import Footer from "../components/Footer";

// --- Context
import { UserContext } from "../context/userContext";
import { useRouter } from "next/router";

const SIWEButton = ({
  className,
  fullWidth,
  login
}: {
  className?: string;
  fullWidth?: boolean;
  login: () => void;
  }) => {
    return (
      <div className={className}>
        <button
            data-testid="connectWalletButton"
            className={`rounded bg-purple-gitcoinpurple px-8 py-3 text-lg text-white ${
              fullWidth ? "w-full" : ""
            }`}
            onClick={login}
          >
            <img
              src="/assets/ethLogo.svg"
              alt="Ethereum Logo"
              className="mr-3 inline h-auto w-4"
            />
            <span className="inline">Sign-in with Ethereum</span>
          </button>
      </div>
    );
}

export default function Home() {
  const { connected, login } = useContext(UserContext);
  const router = useRouter();

  if (connected) {
    router.push("/dashboard/community");
  }

  return (
    <div className="font-libre-franklin flex h-full min-h-default flex-col justify-between bg-purple-darkpurple px-4 text-gray-400 sm:px-24">
      <Header mode="dark" />
      <div className="container mt-6 grow sm:grow-0">
        <div className="mb-14 sm:w-2/3 xl:w-1/2">
          <div className="font-miriam-libre text-white">
            <img src="/assets/gitcoinWordLogo.svg" alt="Gitcoin Logo" />
            <p className="my-2 -ml-1 text-5xl leading-normal sm:text-7xl">
              Passport Scorer
            </p>
          </div>
          <div>
            We all know that Sybil attackers want to sabotage your
            project&apos;s future, but stopping them is really hard and
            expensive if you want to do it on your own. Gitcoin Passport is a
            free, open source tool that gives you Gitcoin-grade Sybil protection
            with only a few lines of code, so you can focus your time, money,
            and attention on growing your business.
          </div>
          <SIWEButton className="mt-10 hidden sm:block" login={login} />
        </div>
      </div>
      <SIWEButton fullWidth={true} className="block w-full sm:hidden" login={login} />
      <Footer mode="dark" />
    </div>
  );
}
