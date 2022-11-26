// --- React components/methods
import React, { useEffect, useState } from "react";

// --- Wagmi
import {
  useAccount,
  useConnect,
} from "wagmi"

// --- Components
import Header from "../components/Header";
import CommunityList from "../components/CommunityList";
import NoCommunities from "../components/NoCommunities";

// --- Types
import { AuthenticationStatus } from "@rainbow-me/rainbowkit";

type DashboardProps = {
  setAuthenticationStatus: Function;
  authenticationStatus: AuthenticationStatus;
}

export type Community = {
  name: string;
  description: string;
}

export default function Dashboard({ setAuthenticationStatus, authenticationStatus }: DashboardProps) {
  const { address } = useAccount();
  const { isLoading } = useConnect();
  const [communities, setCommunities] = useState([
    {
      name: "Gitcoin Grants Protocol",
      description: "Where web3 projects get funded.",
    },
    {
      name: "Bankless",
      description: "Media and Social DAO Onboarding 1 billion people to crypto.",
    },
    {
      name: "Optimism",
      description: "Purchase an .eth name to verify/ connect your existing account."
    }
  ]);
  // const [communities, setCommunities] = useState([]);

  useEffect(() => {
    if (address) {
      setAuthenticationStatus("authenticated");
    } else if (isLoading) {
      setAuthenticationStatus("loading");
    } else {
      setAuthenticationStatus("unauthenticated");
    }
  }, []);

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
   * --> if user has API keys, show them a list of their keys with copy/add/delete buttons and a callout that shows how many keys they have left
   */
  
  return (
    <>
      <div>
        <Header authenticationStatus={authenticationStatus} />
        <div>
          <div className="mt-0 w-full pb-6 text-black p-6 border-b border-gray-300">
            <h1 className="text-2xl font-miriamlibre text-blue-darkblue">Dashboard</h1>
            <p className="mt-2 font-librefranklin text-purple-softpurple">Generate community IDs for specific applications using non-duplication rules like first-in-first-out or last-in-first-out.</p>
          </div>
          <div className="bg-gray-bluegray h-[40rem] md:h-[45rem] flex flex-col">
            {
              communities.length > 0
              ? <CommunityList communities={communities} />
              : <NoCommunities />
            }
          </div>
        </div>
      </div>
    </>
  );
};