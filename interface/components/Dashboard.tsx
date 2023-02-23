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

const QuickLink = ({
  text,
  icon,
  url,
  className,
}: {
  text: React.ReactNode;
  icon?: React.ReactNode;
  url?: string;
  className?: string;
}) => (
  <div
    className={`flex w-full flex-row items-center justify-start border-x border-t border-gray-200 bg-white p-5 ${
      (url ? "cursor-pointer " : " ") + className
    }`}
  >
    <span className="mr-2">{icon}</span>
    {text}
  </div>
);

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
          className="mx-4 border-b border-b-gray-200 bg-white pb-4 sm:mx-20"
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
      <div className="flex grow border-t border-gray-300 px-4 pt-2 sm:px-20">
        <div className="w-64 flex-col">
          <DashboardTabs activeTab={activeTab} />
        </div>
        <div className="flex w-full flex-col p-6">{children}</div>
        <div className="w-96 flex-col text-xs">
          <QuickLink text="Quick Links" />
          <QuickLink
            text="Quick Start Guide"
            url="/"
            icon={<img src="/assets/flagIcon.svg" />}
          />
          <QuickLink
            text="Passport Documentation"
            url="/"
            icon={<img src="/assets/terminalIcon.svg" />}
          />
          <QuickLink
            text="Video Introduction"
            url="/"
            icon={<img src="/assets/playIcon.svg" />}
          />
          <QuickLink
            text="Scorer Documentation"
            url="/"
            icon={<img src="/assets/bookIcon.svg" />}
            className="border-b"
          />
        </div>
      </div>
      <Footer className="px-4 sm:px-20" />
    </div>
  );
}
