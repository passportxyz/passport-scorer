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
  <a
    href={url}
    target="_blank"
    rel="noopener noreferrer"
    className={`flex w-full flex-row items-center justify-start border-gray-200 bg-white p-4 text-xs ${
      (url ? "cursor-pointer text-purple-softpurple " : " ") +
      (url ? "" : "text-purple-darkpurple ") +
      className
    }`}
  >
    {icon}
    {text}
  </a>
);

const QuickLinks = () => {
  const className = "border-b";
  const iconClassName = "mr-2 w-3.5";
  return (
    <div className="w-full rounded border">
      <QuickLink text="Quick Links" className={className} />
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
        url="/"
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
  const linkClassName = "text-base py-2";
  return (
    <div className={className + " rounded border bg-white pb-24"}>
      <QuickLink text="Sample Applications" className="pb-2" />
      <QuickLink
        text="Gitcoin Passports Sample App"
        url="https://github.com/gitcoinco/passport-scorer/tree/main/examples/example-score-a-passport"
        className={linkClassName}
      />
      <QuickLink
        text="Gitcoin Allo Protocol"
        url="https://github.com/gitcoinco/grants-stack/blob/45b6a3a00beb05090e039be2551a06636e873fbc/packages/grant-explorer/src/features/round/PassportConnect.tsx"
        className={linkClassName}
      />
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
      <div className="flex grow flex-row items-center justify-between border-t border-gray-300 px-4 pt-2 sm:px-20 md:flex-row md:items-start">
        {/* Main content - left */}
        <div className="w-48 flex-col items-start self-start">
          <DashboardTabs activeTab={activeTab} />
        </div>

        {/* Main content - center */}
        <div className="grow self-stretch px-6">{children}</div>

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
