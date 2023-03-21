// --- React components/methods
import React, { useState, useEffect, useCallback, useContext } from "react";

// --- Components
import Header from "./Header";
import Footer from "./Footer";

import { DashboardTabs, TabToken } from "./DashboardTabs";

import { Warning } from "./Warning";
import { UserContext } from "../context/userContext";
import {
  BookOpenIcon,
  CommandLineIcon,
  FlagIcon,
  PlayCircleIcon,
} from "@heroicons/react/24/solid";

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
    className={`flex w-full flex-row items-center justify-start border-gray-200  bg-white p-5 ${(url ? "cursor-pointer " : " ") + className
      }`}
  >
    {icon}
    {text}
  </div>
);

const QuickLinks = () => {
  const className = "border-b";
  const iconClassName = "mr-2 w-3.5";
  return (
    <div className="w-full">
      <QuickLink
        text="Quick Links"
        className={className + " text-xs text-gray-500"}
      />
      <QuickLink
        text="Quick Start Guide"
        url="https://docs.passport.gitcoin.co/building-with-passport/quick-start-guide"
        icon={<FlagIcon className={iconClassName} />}
        className={className}
      />
      <QuickLink
        text="Passport Documentation"
        url="https://docs.passport.gitcoin.co/"
        icon={<CommandLineIcon className={iconClassName} />}
        className={className}
      />
      <QuickLink
        text="Video Introduction"
        url="https://www.youtube.com/watch?v=ni7HKq2LcgY"
        icon={<PlayCircleIcon className={iconClassName} />}
        className={className}
      />
      <QuickLink
        text="Scorer Documentation"
        url="https://docs.passport.gitcoin.co/building-with-passport/scorer-api"
        icon={<BookOpenIcon className={iconClassName} />}
        className={className + " border-b-0"}
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

export default function Dashboard({ activeTab, children }: DashboardProps) {
  const { userWarning, setUserWarning } = useContext(UserContext);
  return (
    <div className="font-libre-franklin flex min-h-default flex-col justify-between bg-gray-bluegray text-gray-400">
      {/* The top part of the page */}
      <div className="bg-white">
        <Header className="mx-4 border-b border-b-gray-200 bg-white pb-4 sm:mx-20" />
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
      <div className="flex grow flex-col items-center justify-between border-t border-gray-300 px-4 pt-4 sm:px-20 md:flex-row md:items-start md:pt-6">
        {/* Main content - left */}
        <div className="w-48 flex-col items-start self-start">
          <DashboardTabs activeTab={activeTab} />
        </div>

        {/* Main content - center */}
        <div className="my-6 grow self-stretch md:mx-6 md:my-0">
          {children} <hr className="mt-8 mb-2 md:hidden" />
        </div>

        {/* Main content - right */}
        <div className="w-full flex-col self-stretch text-sm md:max-w-xs">
          <QuickLinks />
          <SampleApplications className="mt-6" />
        </div>
      </div>
      {/* Bottom */}
      <Footer className="px-4 sm:px-20" />
    </div>
  );
}
