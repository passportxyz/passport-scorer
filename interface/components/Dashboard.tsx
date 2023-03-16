// --- React components/methods
import React, { useState, useEffect, useCallback, useContext } from "react";

// --- Components
import Header from "./Header";
import Footer from "./Footer";

import { DashboardTabs, TabToken } from "./DashboardTabs";

import { withPageLayout } from "./PageWidthGrid";

type DashboardProps = {
  activeTab: TabToken;
  children: React.ReactNode;
  setSubheader: (subheader: React.ReactNode) => void;
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
    className={`flex w-full flex-row items-center justify-start border-gray-200  bg-white p-5 ${
      (url ? "cursor-pointer " : " ") + className
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
      <QuickLink
        text="Quick Links"
        className={className + " text-xs text-gray-500"}
      />
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
  return (
    <div className={"text-base " + className}>
      <QuickLink text="Sample Applications" className="text-xs text-gray-500" />
      <QuickLink text="Gitcoin Passports Sample App" url="/" />
      <QuickLink text="Gitcoin Allo Protocol" url="/" />
    </div>
  );
};

export const Subheader = ({}) => {
  return (
    <div className="my-6 w-full bg-white px-4 sm:px-20">
      <h1 className="font-miriamlibre text-2xl text-blue-darkblue">
        Gitcoin Passport Scorer
      </h1>
      <p className="mt-2 font-librefranklin">
        A Scorer is used to score Passports. An API key is required to access
        those scores.
      </p>
    </div>
  );
};

const Dashboard = ({ activeTab, children, setSubheader }: DashboardProps) => {
  useEffect(() => setSubheader(<Subheader />), []);

  return (
    <div className="flex grow flex-col items-center justify-between border-t border-gray-300 px-4 pt-2 sm:px-20 md:flex-row md:items-start">
      {/* Main content - left */}
      <div className="w-48 flex-col items-start self-start">
        <DashboardTabs activeTab={activeTab} />
      </div>

      {/* Main content - center */}
      <div className="my-6 grow self-stretch md:mx-6 md:my-0">{children}</div>

      {/* Main content - right */}
      <div className="w-full flex-col self-stretch text-sm md:max-w-xs">
        <QuickLinks />
        <SampleApplications className="mt-6" />
      </div>
    </div>
  );
};

export default withPageLayout(Dashboard);
