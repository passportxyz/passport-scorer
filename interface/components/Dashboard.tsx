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
  QuestionMarkCircleIcon,
  ChatBubbleBottomCenterTextIcon,
  WindowIcon,
  ListBulletIcon,
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
        icon ? "border-t py-3" : "pt-6 pb-4"
      } ${(url ? "cursor-pointer " : " ") + className}`}
    >
      <span className={`${icon ? "mr-2" : ""}`}>{icon}</span>
      {text}
    </div>
  </a>
);

const General = ({ className }: { className: string }) => {
  const linkClassName = "text-purple-softpurple";
  const iconClassName = "mr-2 w-3.5";
  return (
    <div className={`w-full rounded-md border bg-white ${className}`}>
      <QuickLink
        text="General"
        className="pt-6 text-xs text-purple-darkpurple"
      />
      <QuickLink
        text="Developer Docs"
        url="https://docs.passport.xyz/"
        icon={<BookOpenIcon className={iconClassName} />}
        className={linkClassName}
      />
      <QuickLink
        text="Developer Telegram Group"
        url="https://t.me/passportxyzdevs"
        icon={<ChatBubbleBottomCenterTextIcon className={iconClassName} />}
        className={linkClassName}
      />
      <QuickLink
        text="API Playground"
        url="https://api.scorer.gitcoin.co/docs"
        icon={<CommandLineIcon className={iconClassName} />}
        className={linkClassName}
      />
      <QuickLink
        text="What is a Scorer?"
        url="https://docs.passport.xyz/building-with-passport/passport-api/getting-access#projects-and-project-id"
        icon={<QuestionMarkCircleIcon className={iconClassName} />}
        className={linkClassName}
      />
    </div>
  );
};

const StampsAPI = ({ className }: { className?: string }) => {
  const linkClassName = "text-purple-softpurple";
  const iconClassName = "mr-2 w-3.5";

  return (
    <div
      className={
        "rounded-md border border-gray-lightgray bg-white text-base " +
        className
      }
    >
      <QuickLink
        text="Stamps API"
        className="pt-6 text-xs text-purple-darkpurple"
      />
      <QuickLink
        text="Overview"
        url="https://docs.passport.xyz/building-with-passport/stamps/introduction"
        className={linkClassName}
        icon={<WindowIcon className={iconClassName} />}
      />
      <QuickLink
        text="Quick Start Guide"
        className={linkClassName}
        url="https://docs.passport.xyz/building-with-passport/stamps/quick-start-guide"
        icon={<FlagIcon className={iconClassName} />}
      />
      <QuickLink
        text="API Reference"
        className={linkClassName}
        url="https://docs.passport.xyz/building-with-passport/passport-api/api-reference"
        icon={<ListBulletIcon className={iconClassName} />}
      />
    </div>
  );
};

const ModelsAPI = ({ className }: { className?: string }) => {
  const linkClassName = "text-purple-softpurple";
  const iconClassName = "mr-2 w-3.5";
  return (
    <div
      className={
        "rounded-md border border-gray-lightgray bg-white text-base " +
        className
      }
    >
      <QuickLink
        text="Models API"
        className="pt-6 text-xs text-purple-darkpurple"
      />
      <QuickLink
        text="Overview"
        url="https://docs.passport.xyz/building-with-passport/models"
        className={linkClassName}
        icon={<WindowIcon className={iconClassName} />}
      />
      <QuickLink
        text="API Reference"
        className={linkClassName}
        url="https://docs.passport.xyz/building-with-passport/models/api-reference"
        icon={<ListBulletIcon className={iconClassName} />}
      />
    </div>
  );
};

export const subheader = (
  <div className="my-6 w-full">
    <h1 className="font-miriamlibre text-2xl text-blue-darkblue">
      Human Passport Developer Portal
    </h1>
    <p className="mt-2 font-librefranklin text-purple-softpurple">
      You can use Scorers to organize your integration by use case, and API keys
      to get access to either the Passport or Models API.
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

        <div className="col-span-4 md:col-span-3">
          <General className="col-span-4 md:col-span-3 mb-3" />
          <StampsAPI className="col-span-4 md:col-span-3 mb-3" />
          <ModelsAPI className="col-span-4 md:col-span-3 mb-3" />
        </div>
      </PageWidthGrid>
      <Footer />
    </HeaderContentFooterGrid>
  );
};

export default Dashboard;
