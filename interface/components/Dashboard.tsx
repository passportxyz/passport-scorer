// --- React components/methods
import React, { useState, useEffect, useCallback, useContext } from "react";

// --- Components
import Header from "./Header";
import Footer from "./Footer";

import { DashboardTabs, TabToken } from "./DashboardTabs";

import { Warning } from "./Warning";
import { UserContext } from "../context/userContext";

type DashboardProps = {
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
    className={`flex w-full flex-row items-center justify-start  border-gray-200 bg-white p-5 ${(url ? "cursor-pointer " : " ") + className
      }`}
  >
    <span className="mr-2">{icon}</span>
    {text}
  </div>
);

const QuickLinks = () => {
  const className = "border-x border-t";
  return (
    <div className="w-full">
      <QuickLink text="Quick Links" className={className} />
      <QuickLink
        text="Quick Start Guide"
        url="/"
        icon={<img src="/assets/flagIcon.svg" />}
        className={className}
      />
      <QuickLink
        text="Passport Documentation"
        url="/"
        icon={<img src="/assets/terminalIcon.svg" />}
        className={className}
      />
      <QuickLink
        text="Video Introduction"
        url="/"
        icon={<img src="/assets/playIcon.svg" />}
        className={className}
      />
      <QuickLink
        text="Scorer Documentation"
        url="/"
        icon={<img src="/assets/bookIcon.svg" />}
        className={className + " border-b"}
      />
    </div>
  );
};

const SampleApplications = ({ className }: { className?: string }) => {
  const linkClassName = "text-base";
  return (
    <div className={className}>
      <QuickLink text="Sample Applications" />
      <QuickLink
        text="Gitcoin Passports Sample App"
        url="/"
        className={linkClassName}
      />
      <QuickLink
        text="Gitcoin Allo Protocol"
        url="/"
        className={linkClassName}
      />
    </div>
  );
};

export default function Dashboard({
  activeTab,
  children,
}: DashboardProps) {
  const { userWarning, setUserWarning } = useContext(UserContext);
  return (
    <div className="font-libre-franklin flex min-h-default flex-col justify-between bg-gray-bluegray text-gray-400">
      {/* The top part of the page */}
      <div className="bg-white">
        <Header
          className="mx-4 border-b border-b-gray-200 bg-white pb-4 sm:mx-20"
        />
        {userWarning && (
          <div className="w-full bg-red-100">
            <Warning text={userWarning} onDismiss={() => setUserWarning()} />
          </div>
        )}
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
      {/* The mid part of the page */}
      <div className="flex grow flex-row items-center justify-between border-t border-gray-300 px-4 pt-2 sm:px-20 md:flex-row md:items-start">
        {/* Main content - left */}
        <div className="w-48 flex-col items-start self-start">
          <DashboardTabs activeTab={activeTab} />
        </div>

        {/* Main content - center */}
        <div className="px-6 grow self-stretch">{children}</div>

        {/* Main content - right */}
        <div className="w-full flex-col self-stretch text-sm leading-[18px] md:max-w-xs">
          <QuickLinks />
          <SampleApplications className="mt-6" />
        </div>
      </div>
      {/* Bottom */}
      <Footer className="px-4 sm:px-20" />
    </div>
  );
}
