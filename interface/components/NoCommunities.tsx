// --- React components/methods
import React from "react";

// --- Components
import { RepeatIcon } from "@chakra-ui/icons";

const NoCommunities = ({}): JSX.Element => {
  return (
    <div className="flex flex-col justify-center h-[40rem] md:h-[45rem]">
      <div className="bg-white p-2 w-13 flex mx-auto justify-center text-center rounded-full text-gray-lightgray border mb-8">
        <RepeatIcon viewBox="0 0 25 25" boxSize="1.9em" color="#757087" />
      </div>
      <div className="flex flex-col justify-center text-center align-middle mx-auto">
        <h2 className="text-xl font-miriamlibre text-purple-softpurple mx-auto">My Communities</h2>
        <p className="font-librefranklin mt-2 text-purple-softpurple w-9/12 mx-auto">Manage how your dapps interact with the Gitcoin Passport by creating a key that will connect to any community.</p>
        <button className="mt-6 w-40 pt-1 pb-2 bg-purple-softpurple rounded-md text-white mx-auto">
        <span className="text-xl">+</span> Add
        </button>
      </div>
    </div>
  );
}

export default NoCommunities;
