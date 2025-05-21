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
      className={`rounded bg-purple-gitcoinpurple px-8 py-3 text-lg text-white disabled:cursor-not-allowed disabled:bg-purple-softpurple disabled:text-black ${className}`}
      onClick={login}
      disabled={disabled}
    >
      <img
        src="/assets/ethLogo.svg"
        alt="Ethereum Logo"
        className={`mr-3 inline h-auto w-4 ${disabled ? "invert" : ""}`}
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
    <div className="bg-purple-darkpurple">
      <div className="font-miriam-libre text-white">
        Human Passport
        <p className="md:text-7xl my-2 -ml-1 text-5xl">Developer Portal</p>
      </div>
      <div>
        Human Passport enables users to prove their humanity and other
        reputation signals, and developers to easily use this data to protect
        programs from Sybils and other bad actors.
        <br/>
        <br/>
        Developers can create an API
        key and Scorer via the Developer Portal, which are used to access the
        Human Passport Developer Platform&apos;s APIs.
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
