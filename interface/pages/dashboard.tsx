// --- React methods
import React from "react";

// --- Components
import Header from "../components/Header";

export default function Dashboard() {
  return (
    <>
      <div>
        <Header />
      </div>
      <div className="">
        <div className="mt-0 w-full pb-6 text-black p-6 border-b border-gray-300">
          <h1 className="text-2xl font-miriamlibre">Dashboard</h1>
          <p className="mt-2 font-librefranklin text-gray-600">Generate community IDs for specific applications using non-duplication rules like first-in-first-out or last-in-first-out.</p>
        </div>
      <div className="bg-slate-200 h-screen">
        <div className="text-center flex flex-col justify-center align-middle">
          <h2 className="text-xl font-miriamlibre">My Communities</h2>
          <p className="font-librefranklin mt-2">Manage how your dapps interact with the Gitcoin Passport by creating a key that will connect to any community.</p>
          <button className="mt-6">
            + Create a Key
          </button>
        </div>
      </div>
      </div>
    </>
  );
};