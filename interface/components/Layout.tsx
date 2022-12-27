// --- React components/methods
import React, { useState } from "react";

// --- Next components
import Router, { NextRouter, useRouter } from "next/router";

// --- Components
import Header from "../components/Header";
import { Icon } from "@chakra-ui/icons";
import { HiKey } from "react-icons/hi";
import { IoIosPeople } from "react-icons/io";


type LayoutProps = {
  children: React.ReactNode;
}

export const Layout = ({ children }: LayoutProps) => {
  const router = useRouter();

  const tabbedClasses = (route: string) => {
    const base = "my-4 flex leading-4 cursor-pointer";
    return router.pathname.includes(route) ? `${base} font-bold text-purple-gitcoinviolet bg-white py-2 pr-9 pl-2 rounded-sm` : `${base} text-blue-darkblue`;
  };

  return (
    <div>
        <Header />
        <div>
          <div className="mt-0 w-full border-b border-gray-300 p-6 pb-6 text-black">
            <h1 className="font-miriamlibre text-2xl text-blue-darkblue">
              Scoring Dashboard
            </h1>
            <p className="mt-2 font-librefranklin text-purple-softpurple">
            Create a community and API key to interact with and score eligibility using Gitcoin Passport.
            </p>
          </div>
          <div className="flex bg-gray-bluegray px-6">
            <div className="my-4 min-h-full w-1/5 flex-col">
              <button
                data-testid="communities-tab"
                onClick={() => router.push("/dashboard/community")}
                className={tabbedClasses("community")}
              >
                <Icon as={IoIosPeople} className="mr-2" />Communities
              </button>
              <button
                data-testid="api-keys-tab"
                onClick={() => router.push("/dashboard/api-keys")}
                className={tabbedClasses("api-keys")}
              >
                <Icon as={HiKey} className="mr-2" /> API Keys
              </button>
            </div>
            <div className="flex min-h-full w-full flex-col p-6 md:h-screen">
              {children}
            </div>
          </div>
        </div>
      </div>
  )
};
