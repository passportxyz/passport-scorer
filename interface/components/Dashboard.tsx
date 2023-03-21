// --- React components/methods
import React, { useMemo } from "react";

import DashboardTabs from "./DashboardTabs";
import PageWidthGrid from "../components/PageWidthGrid";
import { useTopLevelPageContext } from "../components/PageLayout";

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
      className={`flex w-full flex-row items-center justify-start border-gray-lightgray  bg-white p-5 ${
        (url ? "cursor-pointer " : " ") + className
      }`}
    >
      <span className="mr-2">{icon}</span>
      {text}
    </div>
  </a>
);

const QuickLinks = ({ className }: { className: string }) => {
  const linkClassName = "border-x border-t";
  const iconClassName = "mr-2 w-3.5";
  return (
    <div className={`w-full ${className}`}>
      <QuickLink
        text="Quick Links"
        className={linkClassName + " rounded-t-md pt-6 text-xs text-gray-500"}
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
        className={linkClassName + " rounded-b-md border-b"}
      />
    </div>
  );
};

const SampleApplications = ({ className }: { className?: string }) => {
  return (
    <div className={"border-gray-lightgray text-base " + className}>
      <QuickLink
        text="Sample Applications"
        className="rounded-t-md border-x border-t pt-6 text-xs text-gray-500"
      />
      <QuickLink
        text="Gitcoin Passports Sample App"
        url="/"
        className="border-x"
      />
      <QuickLink
        text="Gitcoin Allo Protocol"
        className="rounded-b-md border-x border-b"
        url="/"
      />
    </div>
  );
};

export const Subheader = ({}) => {
  return (
    <div className="my-6 w-full">
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

const Dashboard = () => {
  const { generateHeader, generateFooter } = useTopLevelPageContext();
  const PageHeader = useMemo(() => generateHeader(Subheader), [generateHeader]);
  const PageFooter = useMemo(() => generateFooter(), [generateFooter]);

  return (
    <>
      <PageHeader />
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
      <PageFooter />
    </>
  );
};

export default Dashboard;
