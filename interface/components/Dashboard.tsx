// --- React components/methods
import React, { useMemo } from "react";

// --- Components
import Header from "./Header";
import Footer from "./Footer";

import { DashboardTabs, TabToken } from "./DashboardTabs";

import PageWidthGrid, {
  withPageLayout,
  TopLevelPageParams,
} from "./PageWidthGrid";

type DashboardProps = TopLevelPageParams & {
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
    className={`flex w-full flex-row items-center justify-start border-gray-200  bg-white p-5 ${
      (url ? "cursor-pointer " : " ") + className
    }`}
  >
    <span className="mr-2">{icon}</span>
    {text}
  </div>
);

const QuickLinks = ({ className }: { className: string }) => {
  const linkClassName = "border-x border-t";
  return (
    <div className={`w-full ${className}`}>
      <QuickLink
        text="Quick Links"
        className={linkClassName + " text-xs text-gray-500"}
      />
      <QuickLink
        text="Quick Start Guide"
        url="/"
        icon={<img src="/assets/flagIcon.svg" />}
        className={linkClassName}
      />
      <QuickLink
        text="Passport Documentation"
        url="/"
        icon={<img src="/assets/terminalIcon.svg" />}
        className={linkClassName}
      />
      <QuickLink
        text="Video Introduction"
        url="/"
        icon={<img src="/assets/playIcon.svg" />}
        className={linkClassName}
      />
      <QuickLink
        text="Scorer Documentation"
        url="/"
        icon={<img src="/assets/bookIcon.svg" />}
        className={linkClassName + " border-b"}
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

const Dashboard = ({
  activeTab,
  children,
  generateHeader,
  generateFooter,
}: DashboardProps) => {
  const PageHeader = useMemo(() => generateHeader(Subheader), [generateHeader]);
  const PageFooter = useMemo(() => generateFooter(), [generateFooter]);

  return (
    <>
      <PageHeader />
      <PageWidthGrid className="mt-4 h-fit">
        <div className="col-span-2 col-start-1 flex-col items-start xl:row-span-2">
          <DashboardTabs activeTab={activeTab} />
        </div>

        {/* Spacer in lg */}
        <div className="lg:col-span-6 xl:hidden" />

        <div className="col-span-4 md:col-span-6 lg:col-span-5 lg:row-span-2 xl:col-span-7">
          {children}
        </div>

        <QuickLinks className="col-span-4 md:col-span-3" />
        <SampleApplications className="col-span-4 md:col-span-3" />
      </PageWidthGrid>
      <PageFooter />
    </>
  );
};

export default withPageLayout(Dashboard);
