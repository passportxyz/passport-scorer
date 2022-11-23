// --- React methods
import React from "react";

// --- Components
import Header from "../components/Header";
import { RepeatIcon } from "@chakra-ui/icons";

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
        <div className="bg-slate-200 h-[40rem] md:h-[45rem] flex flex-col  justify-center">
          <div className="bg-white p-2 w-13 flex text-center mx-auto rounded-full border-gray-300 border mb-8">
            <RepeatIcon viewBox="0 0 25 25" boxSize="1.9em" color={"gray.500"} />
          </div>
          <div className="flex flex-col justify-center text-center align-middle mx-auto">
            <h2 className="text-xl font-miriamlibre text-slate-600 mx-auto">My Communities</h2>
            <p className="font-librefranklin mt-2 text-slate-600 w-9/12 mx-auto">Manage how your dapps interact with the Gitcoin Passport by creating a key that will connect to any community.</p>
            <button className="mt-6 w-40 pt-1 pb-2 bg-slate-600 rounded-md text-white mx-auto">
            <span className="text-xl">+</span> Create a Key
            </button>
          </div>
        </div>
      </div>
    </>
  );
};