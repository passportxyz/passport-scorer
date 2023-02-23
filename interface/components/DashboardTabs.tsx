// --- React components/methods
import React from "react";

import { useRouter } from "next/router";

// --- Components
import { SettingsIcon, Icon } from "@chakra-ui/icons";
import { GoInbox } from "react-icons/go";

export type TabToken = "scorer" | "api-keys";

const TabButton = ({
  icon,
  text,
  token,
  selected,
  router,
}: {
  icon: React.ReactNode;
  text: React.ReactNode;
  token: TabToken;
  selected?: boolean;
  router: any;
}) => (
  <button
    onClick={() => router.push(`/dashboard/${token}`)}
    className={`m-2 flex w-full items-center justify-start rounded-sm border p-3 text-blue-darkblue ${
      selected ? "border-gray-300 bg-white" : "border-gray-100 "
    }`}
  >
    <span className={`mr-2 ${selected ? "text-purple-gitcoinpurple" : ""}`}>
      {icon}
    </span>
    {text}
  </button>
);
export const DashboardTabs = ({ activeTab }: { activeTab: TabToken }) => {
  const router = useRouter();
  return (
    <>
      <TabButton
        icon={<Icon as={GoInbox} />}
        text="Scorer"
        data-testid="scorer-tab"
        token="scorer"
        selected={activeTab === "scorer"}
        router={router}
      />
      <TabButton
        icon={<SettingsIcon />}
        text="API Keys"
        data-testid="api-keys-tab"
        token="api-keys"
        selected={activeTab === "api-keys"}
        router={router}
      />
    </>
  );
};
