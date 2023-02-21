// --- React components/methods
import React, { useState, useEffect, useCallback } from "react";

// --- Wagmi
// import { useAccount, useConnect } from "wagmi";
import { useRouter } from "next/router";

// --- Components
import Header from "../components/Header";
import Footer from "../components/Footer";
import { SettingsIcon, Icon } from "@chakra-ui/icons";
import { GoInbox } from "react-icons/go";

// --- Types
import { AuthenticationStatus } from "@rainbow-me/rainbowkit";

type DashboardProps = {
  // setAuthenticationStatus?: Function;
  authenticationStatus: AuthenticationStatus;
  activeTab: string;
  children: React.ReactNode;
};

export default function Dashboard({
  // setAuthenticationStatus,
  authenticationStatus,
  activeTab,
  children,
}: DashboardProps) {
  const router = useRouter();

  const tabbedClasses = (tab: string) => {
    const base = "my-4 flex leading-4 cursor-pointer";
    return tab === activeTab
      ? `${base} font-bold font-blue-darkblue`
      : `${base} text-purple-softpurple`;
  };

  return (
    <div className="font-libre-franklin flex h-full min-h-default flex-col justify-between bg-gray-bluegray text-gray-400">
      <div className="bg-white px-4 sm:px-20">
        <Header authenticationStatus={authenticationStatus} />
        <div className="my-6 w-full text-black">
          <h1 className="font-miriamlibre text-2xl text-blue-darkblue">
            Dashboard
          </h1>
          <p className="mt-2 font-librefranklin text-purple-softpurple">
            Generate community IDs for specific applications using
            non-duplication rules like first-in-first-out or last-in-first-out.
          </p>
        </div>
      </div>
      <div className="flex border-t border-gray-300 px-4 sm:px-20">
        <div className="my-4 w-1/5 flex-col">
          <button
            data-testid="communities-tab"
            onClick={() => router.push("/dashboard/community")}
            className={tabbedClasses("community")}
          >
            <Icon as={GoInbox} className="mr-2" />
            Communities
          </button>
          <button
            data-testid="api-keys-tab"
            onClick={() => router.push("/dashboard/api-keys")}
            className={tabbedClasses("api-keys")}
          >
            <SettingsIcon className="mr-2" /> API Keys
          </button>
        </div>
        <div className="flex h-screen w-full flex-col p-6">{children}</div>
      </div>
      <div className="px-4 sm:px-20">
        <Footer />
      </div>
    </div>
  );
}
