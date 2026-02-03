// --- React Methods
import React, { useContext, useEffect } from "react";
import { useNavigate } from "react-router-dom";

// --- Context
import { UserContext } from "../context/userContext";

const SIWEButton = ({
  className,
  login,
  testId,
  disabled,
}: {
  className?: string;
  login: () => void;
  testId: string;
  disabled?: boolean;
}) => {
  return (
    <button
      data-testid={testId}
      className={`rounded-[12px] bg-black px-8 py-3 text-lg text-white font-medium transition-all duration-200 hover:bg-gray-800 disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-gray-400 ${className}`}
      onClick={login}
      disabled={disabled}
    >
      <img
        src="/assets/ethLogo.svg"
        alt="Ethereum Logo"
        className={`mr-3 inline h-auto w-4 ${disabled ? "opacity-50" : ""}`}
      />
      <span className="inline">
        {disabled ? "Loading..." : "Sign-in with Ethereum"}
      </span>
    </button>
  );
};

const LandingPage = () => {
  const { connected, ready, authenticating, login } = useContext(UserContext);
  const navigate = useNavigate();

  useEffect(() => {
    if (connected) {
      navigate("dashboard/scorer");
    }
  }, [connected]);

  const authenticationOverlay = authenticating && (
    <div className="absolute top-0 left-0 z-10 h-screen w-full bg-black bg-opacity-60" />
  );

  const mainContent = (
    <div className="bg-white rounded-[16px] p-8 shadow-card">
      <div className="font-heading text-gray-900">
        <img src="/assets/gitcoinWordLogo.svg" alt="Human Logo" />
        <p className="md:text-7xl my-2 -ml-1 text-5xl font-bold">Passport Scorer</p>
      </div>
      <div className="text-gray-600 mt-4 leading-relaxed">
        Human Passport is a Sybil defense tool that makes it easy to protect
        your web3 community from bots and bad actors. Connect your wallet below
        to access the Passport Scorer app, which helps you create a
        &quot;Scorer&quot; for the application you want to protect from Sybil
        attackers.
      </div>
      <SIWEButton
        className="mt-10 hidden md:block"
        login={login}
        testId="connectWalletButtonDesktop"
        disabled={!ready}
      />
    </div>
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
          disabled={!ready}
          testId="connectWalletButtonMobile"
        />
      </div>
    </>
  );
};

export default LandingPage;
