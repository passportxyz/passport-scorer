// --- React components/methods
import React from "react";

import { useRouter } from "next/router";

// --- Components
import { SettingsIcon, Icon, StarIcon } from "@chakra-ui/icons";

export type TabToken = "scorer" | "api-keys";

type TabButtonProps = {
  icon: React.ReactNode;
  text: React.ReactNode;
  token: TabToken;
  selected?: boolean;
  router: any;
  className?: string;
};

const TabButton = ({
  icon,
  text,
  token,
  selected,
  router,
  className,
}: TabButtonProps) => (
  <button
    data-testid={`${token}-tab`}
    onClick={() => router.push(`/dashboard/${token}`)}
    className={`flex w-full items-center justify-start rounded-sm border p-3 text-blue-darkblue ${
      (selected ? "border-gray-200 bg-white " : "border-gray-100 ") + className
    }`}
  >
    <span className={`mr-2 ${selected ? "text-purple-gitcoinpurple" : ""}`}>
      {icon}
    </span>
    {text}
  </button>
);

type TabProps = {
  icon: React.ReactNode;
  text: string;
  token: TabToken;
};

const tabInfo: TabProps[] = [
  {
    icon: <StarIcon />,
    text: "Scorer",
    token: "scorer",
  },
  {
    icon: <SettingsIcon />,
    text: "API Keys",
    token: "api-keys",
  },
];

const TabButtonList = ({
  activeTab,
  router,
}: {
  activeTab: TabToken;
  router: any;
}) => (
  <div>
    {tabInfo.map(({ icon, text, token }, idx) => (
      <TabButton
        icon={icon}
        text={text}
        token={token}
        selected={activeTab === token}
        router={router}
        className={idx === 0 ? "mb-2" : ""}
        key={token}
      />
    ))}
  </div>
);

const TabSelect = ({
  activeTab,
  router,
}: {
  activeTab: TabToken;
  router: any;
}) => (
  // Mobile doesn't respect py on the select element, so adding some here on this div. But leaving
  // most on the select element b/c much better experience on desktop b/c of bounding box.
  // Some browsers will use this "label" element area all as a click target, which is ideal.
  <label
    htmlFor="tabSelect"
    className="flex items-center rounded-sm border border-gray-200 bg-white py-1 pr-1 mb-6 md:hidden"
  >
    <div className="ml-3 -mt-1 text-purple-gitcoinpurple">
      {tabInfo.find((tab) => tab.token === activeTab)?.icon}
    </div>
    <select
      id="tabSelect"
      value={activeTab}
      onChange={(e) => router.push(`/dashboard/${e.target.value}`)}
      className="flex w-full justify-around bg-white py-3 pl-2 text-blue-darkblue"
    >
      {tabInfo.map(({ text, token }) => (
        <option
          color="purple"
          value={token}
          key={token}
          className="text-blue-darkblue"
        >
          {text}
        </option>
      ))}
    </select>
  </label>
);

export const DashboardTabs = ({ activeTab }: { activeTab: TabToken }) => {
  const router = useRouter();
  return (
    <>
      <div className="block md:hidden">
        <TabSelect activeTab={activeTab} router={router} />
      </div>
      <div className="hidden md:block">
        <TabButtonList activeTab={activeTab} router={router} />
      </div>
    </>
  );
};
