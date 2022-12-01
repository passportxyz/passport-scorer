// --- React components/methods
import React, { useState } from "react";

// --- Wagmi
// import { useAccount, useConnect } from "wagmi";

// --- Components
import Header from "../components/Header";
import CommunityList from "../components/CommunityList";
import NoCommunities from "../components/NoCommunities";
import { SettingsIcon, Icon } from "@chakra-ui/icons";
import { GoInbox } from "react-icons/go"

// --- Types
import { AuthenticationStatus } from "@rainbow-me/rainbowkit";
import { ApiKeyList } from "../components/APIKeyList";

type DashboardProps = {
  // setAuthenticationStatus?: Function;
  authenticationStatus: AuthenticationStatus;
};

export type Community = {
  name: string;
  description: string;
};

export default function Dashboard({
  // setAuthenticationStatus,
  authenticationStatus,
}: DashboardProps) {
  const [activeTab, setActiveTab] = useState("communities");
  // const { address } = useAccount();
  // const { isLoading } = useConnect();

  // Mock -- communities
  // const [communities, setCommunities] = useState([
  //   {
  //     name: "Gitcoin Grants Protocol",
  //     description: "Where web3 projects get funded.",
  //   },
  //   {
  //     name: "Bankless",
  //     description: "Media and Social DAO Onboarding 1 billion people to crypto.",
  //   },
  //   {
  //     name: "Optimism",
  //     description: "Purchase an .eth name to verify/ connect your existing account."
  //   }
  // ]);

  // Mock -- no communities
  const [communities, setCommunities] = useState([]);

  /**
   * @TODO
   * --> if user is authenticated, show them their dashboard -- if user is unauthenticated, show them the default dashboard
   * --> Or -- make it so that if a user is unauthenticated they're automatically routed back to the Home page
   */

  /**
   * @TODO
   * --> if user has communities, list those communities -- otherwise show the default dashboard UI
   */

  /**
   * @TODO
   * --> when user clicks on "Add", a modal pops up where they can create a new Community
   * --> sends POST request to backend where a new Community will be created in db
   */

  /**
   * @TODO
   * --> when user clicks on "Create a Key", a modal pops up -- that connects to an auto-generated API key in the BE -- and allows user to assign a name to the key and save it to their account
   */

  /**
   * @TODO
   * --> if user has communities, show them the "Create key" button in the top part of the page
   */

  /**
   * @TODO
   * --> if user has API keys:
   * - [] show them a list of their keys with copy buttons & delete buttons
   * - [] callout that shows how many keys they have left
   */

  const tabbedClasses = (tab: string) => {
    const base = "my-4 flex leading-4 cursor-pointer";
    return tab === activeTab ? `${base} font-bold font-blue-darkblue` : `${base} text-purple-softpurple`;
  };

  return (
    <>
      <div>
        <Header authenticationStatus={authenticationStatus} />
        <div>
          <div className="mt-0 w-full border-b border-gray-300 p-6 pb-6 text-black">
            <h1 className="font-miriamlibre text-2xl text-blue-darkblue">
              Dashboard
            </h1>
            <p className="mt-2 font-librefranklin text-purple-softpurple">
              Generate community IDs for specific applications using
              non-duplication rules like first-in-first-out or
              last-in-first-out.
            </p>
          </div>
          <div className="flex bg-gray-bluegray px-6">
            <div className="my-4 min-h-full w-1/5 flex-col border-r border-gray-lightgray">
              <button
                data-testid="communities-tab"
                onClick={() => setActiveTab("communities")}
                className={tabbedClasses("communities")}
              >
                <Icon as={GoInbox} className="mr-2" />Communities
              </button>
              <button
                data-testid="api-keys-tab"
                onClick={() => setActiveTab("apiKeys")}
                className={tabbedClasses("apiKeys")}
              >
                <SettingsIcon className="mr-2" /> API Keys
              </button>
            </div>
            <div className="flex min-h-full w-full flex-col p-6 md:h-screen">
              {activeTab === "communities" ? (
                <>
                  {communities.length > 0 ? (
                    <CommunityList communities={communities} />
                  ) : (
                    <NoCommunities />
                  )}
                </>
              ) : (
                <ApiKeyList />
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
