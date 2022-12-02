// --- React components/methods
import React from "react";

// --- Components
import { RepeatIcon } from "@chakra-ui/icons";

const NoCommunities = ({
  addRequest,
}: {
  addRequest: () => void;
}): JSX.Element => {
  return (
    <div className="flex h-[40rem] flex-col justify-center md:h-[45rem]">
      <div className="w-13 mx-auto mb-8 flex justify-center rounded-full border bg-white p-2 text-center text-gray-lightgray">
        <RepeatIcon viewBox="0 0 25 25" boxSize="1.9em" color="#757087" />
      </div>
      <div className="mx-auto flex flex-col justify-center text-center align-middle">
        <h2 className="mx-auto font-miriamlibre text-xl text-purple-softpurple">
          My Communities
        </h2>
        <p className="mx-auto mt-2 w-9/12 font-librefranklin text-purple-softpurple">
          Manage how your dapps interact with the Gitcoin Passport by creating a
          key that will connect to any community.
        </p>
        <button
          onClick={addRequest}
          className="mx-auto mt-6 w-40 rounded-md bg-purple-softpurple pt-1 pb-2 text-white"
        >
          <span className="text-xl">+</span> Add
        </button>
      </div>
    </div>
  );
};

export default NoCommunities;
