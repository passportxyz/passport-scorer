// --- React components/methods
import React from "react";

import DashboardTabs from "./DashboardTabs";
import PageWidthGrid from "./PageWidthGrid";
import HeaderContentFooterGrid from "./HeaderContentFooterGrid";
import Header from "./Header";
import Footer from "./Footer";

import { Outlet } from "react-router-dom";

import {
  BookOpenIcon,
  CommandLineIcon,
  FlagIcon,
  PlayCircleIcon,
} from "@heroicons/react/24/solid";

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
  <a href={url} target="_blank" rel="noreferrer">
    <div
      className={`flex w-full flex-row items-center justify-start border-gray-lightgray px-6 ${
        icon ? "py-3 border-t" : "pt-6 pb-4"
      } ${(url ? "cursor-pointer " : " ") + className}`}
    >
      <span className={`${icon ? "mr-2" : ""}`}>{icon}</span>
      {text}
    </div>
  </a>
);

const QuickLinks = ({ className }: { className: string }) => {
  const linkClassName = "text-purple-softpurple";
  const iconClassName = "mr-2 w-3.5";
  return (
    <div className={`w-full bg-white border rounded-md ${className}`}>
      <QuickLink
        text="Quick Links"
        className="pt-6 text-xs text-purple-darkpurple"
      />
      <QuickLink
        text="Quick Start Guide"
        url="https://docs.passport.gitcoin.co/building-with-passport/quick-start-guide"
        icon={<FlagIcon className={iconClassName} />}
        className={linkClassName}
      />
      <QuickLink
        text="Passport Documentation"
        url="https://docs.passport.gitcoin.co/"
        icon={<CommandLineIcon className={iconClassName} />}
        className={linkClassName}
      />
      <QuickLink
        text="Video Introduction"
        url="https://www.youtube.com/watch?v=ni7HKq2LcgY"
        icon={<PlayCircleIcon className={iconClassName} />}
        className={linkClassName}
      />
      <QuickLink
        text="Scorer Documentation"
        url="https://docs.passport.gitcoin.co/building-with-passport/scorer-api"
        icon={<BookOpenIcon className={iconClassName} />}
        className={linkClassName}
      />
    </div>
  );
};

const SampleApplications = ({ className }: { className?: string }) => {
  const classOverwrite = "py-2"
  return (
    <div className={"border-gray-lightgray border rounded-md bg-white text-base pb-24 " + className}>
      <QuickLink
        text="Sample Applications"
        className="pt-6 text-xs text-purple-darkpurple"
      />
      <QuickLink
        text="Gitcoin Passport Sample App"
        url="https://github.com/gitcoinco/passport-scorer/tree/main/examples/example-score-a-passport"
        className="text-purple-softpurple pt-0"
      />
      <QuickLink
        text="Gitcoin Allo Protocol"
        className="text-purple-softpurple pt-0 pb-2"
        url="https://github.com/gitcoinco/grants-stack/blob/45b6a3a00beb05090e039be2551a06636e873fbc/packages/grant-explorer/src/features/round/PassportConnect.tsx"
      />
    </div>
  );
};

export const subheader = (
  <div className="my-6 w-full">
    <h1 className="font-miriamlibre text-2xl text-blue-darkblue">
      Gitcoin Passport Scorer
    </h1>
    <p className="mt-2 font-librefranklin text-purple-softpurple">
      A Scorer is used to score Passports. An API key is required to access
      those scores.
    </p>
  </div>
);

const Dashboard = () => {
  return (
    <HeaderContentFooterGrid>
      <Header subheader={subheader} />
      <PageWidthGrid className="mt-4 h-fit">
        <DashboardTabs className="col-span-2 col-start-1 flex-col items-start xl:row-span-2" />

        {/* Spacer in lg */}
        <div className="lg:col-span-6 xl:hidden" />

        <div className="col-span-4 md:col-span-6 lg:col-span-5 lg:row-span-2 xl:col-span-7">
          <Outlet />
        </div>

        <QuickLinks className="col-span-4 md:col-span-3" />
        <SampleApplications className="col-span-4 md:col-span-3" />
      </PageWidthGrid>
      <Footer />
    </HeaderContentFooterGrid>
  );
};

export default Dashboard;
