// --- React components/methods
import React from "react";

// --- Components
import {
  Grid, GridItem
} from "@chakra-ui/react"
import CommunityCard from "./CommunityCard";

// --- Types
import { Community } from "../pages/dashboard";

type CommunityListProps = {
  communities: Community[];
}

const CommunityList = ({ communities }: CommunityListProps): JSX.Element => {
  const communityList = communities.map((community: Community) => {
    return (
      <CommunityCard community={community} />
    );
  });

  return (
    <div className="mt-10 mx-11">
      <p className="text-purple-softpurple mb-3 font-librefranklin font-semibold">My Communities</p>
      {communityList}
      
      <button className="text-blue-darkblue font-librefranklin text-md border border-gray-lightgray py-2 px-6 rounded-sm mt-5"><span className="text-lg">+</span> Add</button>
    </div>
  );
};

export default CommunityList;
