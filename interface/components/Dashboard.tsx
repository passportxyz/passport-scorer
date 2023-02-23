// --- React components/methods
import React, { useState, useEffect, useCallback } from "react";

// --- Components
import Header from "./Header";
import Footer from "./Footer";

import { DashboardTabs, TabToken } from "./DashboardTabs";

// --- Types
import { AuthenticationStatus } from "@rainbow-me/rainbowkit";

type DashboardProps = {
  // setAuthenticationStatus?: Function;
  authenticationStatus: AuthenticationStatus;
  activeTab: TabToken;
  children: React.ReactNode;
};

export default function Dashboard({
  // setAuthenticationStatus,
  authenticationStatus,
  activeTab,
  children,
}: DashboardProps) {
  return (
    <div className="font-libre-franklin flex h-full min-h-default flex-col justify-between bg-gray-bluegray text-gray-400">
      <div className="bg-white">
        <Header
          authenticationStatus={authenticationStatus}
          className="mx-4 border-b border-b-gray-300 bg-white pb-4 sm:mx-20"
        />
        <div className="w-full bg-red-100">{/* ERROR ALERT HERE */}</div>
        <div className="my-6 w-full bg-white px-4 sm:px-20">
          <h1 className="font-miriamlibre text-2xl text-blue-darkblue">
            Gitcoin Passport Scorer
          </h1>
          <p className="mt-2 font-librefranklin">
            A Scorer is used to score Passports. An API key is required to
            access those scores.
          </p>
        </div>
      </div>
      <div className="flex grow border-t border-gray-300 px-4 sm:px-20">
        <div className="w-64 flex-col">
          <DashboardTabs activeTab={activeTab} />
        </div>
        <div className="flex w-full flex-col p-6">{children}</div>
      </div>
      <Footer className="px-4 sm:px-20" />
    </div>
  );
}
