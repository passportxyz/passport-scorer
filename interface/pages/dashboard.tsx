// --- React methods
import React, { useEffect } from "react";

// --- Wagmi
import {
  useAccount,
  useConnect,
} from "wagmi"

// --- Components
import Header from "../components/Header";
import { RepeatIcon } from "@chakra-ui/icons";

// --- Types
import { AuthenticationStatus } from "@rainbow-me/rainbowkit";

type DashboardProps = {
  setAuthenticationStatus: Function;
  authenticationStatus: AuthenticationStatus;
}

export default function Dashboard({ setAuthenticationStatus, authenticationStatus }: DashboardProps) {
  const { address } = useAccount();
  const { isLoading } = useConnect();

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
   * @TODO : if user is authenticated, show them their dashboard -- if user is unauthenticated, show them the default dashboard
   * Or -- make it so that if a user is unauthenticated they're automatically routed back to the Home page
   */

  /**
   * @TODO : if user has communities, list those communities -- otherwise show the default dashboard UI
   */

  /**
   * @TODO : when user clicks on "Create a Key", a modal pops up containing an auto-generated key pulled in from the backend(?)
   */
  
  return (
    <>
      <div>
        <Header />
      </div>
      <div className="">
        <div className="mt-0 w-full pb-6 text-black p-6 border-b border-gray-300">
          <h1 className="text-2xl font-miriamlibre text-blue-darkblue">Dashboard</h1>
          <p className="mt-2 font-librefranklin text-purple-softpurple">Generate community IDs for specific applications using non-duplication rules like first-in-first-out or last-in-first-out.</p>
        </div>
        <div className="bg-gray-bluegray h-[40rem] md:h-[45rem] flex flex-col  justify-center">
          <div className="bg-white p-2 w-13 flex text-center mx-auto rounded-full border-gray-300 border mb-8">
            <RepeatIcon viewBox="0 0 25 25" boxSize="1.9em" color={"gray.500"} />
          </div>
          <div className="flex flex-col justify-center text-center align-middle mx-auto">
            <h2 className="text-xl font-miriamlibre text-purple-softpurple mx-auto">My Communities</h2>
            <p className="font-librefranklin mt-2 text-purple-softpurple w-9/12 mx-auto">Manage how your dapps interact with the Gitcoin Passport by creating a key that will connect to any community.</p>
            <button className="mt-6 w-40 pt-1 pb-2 bg-purple-softpurple rounded-md text-white mx-auto">
            <span className="text-xl">+</span> Add
            </button>
          </div>
        </div>
      </div>
    </>
  );
};