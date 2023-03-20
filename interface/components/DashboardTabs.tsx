// --- React components/methods
import React from "react";

// --- React Router
import { useNavigate } from "react-router-dom";

// --- Components
import { Cog8ToothIcon, StarIcon } from "@heroicons/react/24/solid";

export type TabToken = "scorer" | "api-keys";

type TabButtonProps = {
  icon: React.ReactNode;
  text: React.ReactNode;
  token: TabToken;
  selected?: boolean;
  navigate: (to:string) => void;
  className?: string;
};

const TabButton = ({
  icon,
  text,
  token,
  selected,
  navigate,
  className,
}: TabButtonProps) => (
  <button
    data-testid={`${token}-tab`}
    onClick={() => navigate(`/dashboard/${token}`)}
    className={`flex w-full items-center justify-start rounded-sm px-3 py-2 text-blue-darkblue ${
      (selected ? "rounded border border-gray-lightgray bg-white " : " ") +
      className
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
    icon: <StarIcon className="w-5" />,
    text: "Scorer",
    token: "scorer",
  },
  {
    icon: <Cog8ToothIcon className="w-5" />,
    text: "API Keys",
    token: "api-keys",
  },
];

const TabButtonList = ({
  activeTab,
  navigate,
}: {
  activeTab: TabToken;
  navigate: (to:string) => void;
}) => (
  <div>
    {tabInfo.map(({ icon, text, token }, idx) => (
      <TabButton
        icon={icon}
        text={text}
        token={token}
        selected={activeTab === token}
        navigate={navigate}
        className={idx === 0 ? "mb-2" : ""}
        key={token}
      />
    ))}
  </div>
);

const TabSelect = ({
  activeTab,
  navigate,
}: {
  activeTab: TabToken;
  navigate: (to:string) => void;
}) => (
  // Mobile doesn't respect py on the select element, so adding some here on this div. But leaving
  // most on the select element b/c much better experience on desktop b/c of bounding box.
  // Some browsers will use this "label" element area all as a click target, which is ideal.
  <label
    htmlFor="tabSelect"
    className="flex items-center rounded-sm border border-gray-200 bg-white py-1 pr-1 md:hidden"
  >
    <div className="ml-3 -mt-1 text-purple-gitcoinpurple">
      {tabInfo.find((tab) => tab.token === activeTab)?.icon}
    </div>
    <select
      id="tabSelect"
      value={activeTab}
      onChange={(e) => navigate(`/dashboard/${e.target.value}`)}
      className="ml-2 flex w-full justify-around bg-white py-2 text-blue-darkblue"
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
  const navigate = useNavigate();
  return (
    <>
      <div className="block md:hidden">
        <TabSelect activeTab={activeTab} navigate={navigate} />
      </div>
      <div className="hidden md:block">
        <TabButtonList activeTab={activeTab} navigate={navigate} />
      </div>
    </>
  );
};
