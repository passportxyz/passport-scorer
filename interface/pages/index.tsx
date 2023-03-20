// --- React Methods
import React, { useState, useRef, useContext, useEffect } from "react";

// --- Context
import { UserContext } from "../context/userContext";
import { useRouter } from "next/router";
import { useToast } from "@chakra-ui/react";

import withHomePageLayout from "../components/withHomePageLayout";

const SIWEButton = ({
  className,
  fullWidth,
  login,
  testId,
}: {
  className?: string;
  fullWidth?: boolean;
  login: () => void;
  testId: string;
}) => {
  return (
    <button
      data-testid={testId}
      className={`rounded bg-purple-gitcoinpurple px-8 py-3 text-lg text-white ${className}`}
      onClick={login}
    >
      <img
        src="/assets/ethLogo.svg"
        alt="Ethereum Logo"
        className="mr-3 inline h-auto w-4"
      />
      <span className="inline">Sign-in with Ethereum</span>
    </button>
  );
};

const Home = () => {
  const { connected, authenticating, login, loginComplete } =
    useContext(UserContext);
  const router = useRouter();
  const toast = useToast();

  if (connected) {
    router.push("/dashboard/scorer");
  }

  useEffect(() => {
    if (loginComplete) {
      toast({
        duration: 5000,
        isClosable: true,
        render: (result: any) => (
          <div className="flex justify-between rounded-md bg-blue-darkblue p-4 text-white">
            <span className="step-icon step-icon-completed flex h-9 items-center">
              <span className="relative z-10 flex h-8 w-8 items-center justify-center rounded-full bg-teal-600">
                <img
                  alt="completed icon"
                  className="sticky top-0 h-6"
                  src="/assets/white-check-icon.svg"
                />
              </span>
            </span>
            <p className="py-1 px-3">Ethereum account has been validated.</p>
            <button className="sticky top-0" onClick={result.onClose}>
              <img
                alt="close button"
                className="rounded-lg hover:bg-gray-500"
                src="/assets/x-icon.svg"
              />
            </button>
          </div>
        ),
      });
    }
  }, [loginComplete]);

  const authenticationOverlay = authenticating && (
    <div className="absolute top-0 left-0 z-10 h-screen w-full bg-black bg-opacity-60" />
  );

  const mainContent = (
    <>
      <div className="font-miriam-libre text-white">
        <img src="/assets/gitcoinWordLogo.svg" alt="Gitcoin Logo" />
        <p className="md:text-7xl my-2 -ml-1 text-5xl">Passport Scorer</p>
      </div>
      <div>
        We all know that Sybil attackers want to sabotage your project&apos;s
        future, but stopping them is really hard and expensive if you want to do
        it on your own. Gitcoin Passport is a free, open source tool that gives
        you Gitcoin-grade Sybil protection with only a few lines of code, so you
        can focus your time, money, and attention on growing your business.
      </div>
      <SIWEButton
        className="mt-10 hidden md:block"
        login={login}
        testId="connectWalletButtonDesktop"
      />
    </>
  );

  return (
    <>
      {authenticationOverlay}
      <div className="col-span-4 mb-14 justify-self-center md:self-center xl:col-span-6">
        {mainContent}
      </div>
      <div className="col-span-4 grid h-full grid-rows-[1fr_auto] md:hidden">
        <div></div>
        <SIWEButton
          className="col-span-4 block md:hidden"
          login={login}
          testId="connectWalletButtonMobile"
        />
      </div>
    </>
  );
};

export default withHomePageLayout(Home);
