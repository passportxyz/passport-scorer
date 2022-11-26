// --- React components/methods
import React from "react";

// --- Components
import CommunityCard from "./CommunityCard";
import ModalTemplate from "./ModalTemplate";
import { useDisclosure } from "@chakra-ui/react";

// --- Types
import { Community } from "../pages/dashboard";

type CommunityListProps = {
  communities: Community[];
}

/**
 * 
 * @TODO --> Finish adding Modal for 'Add community'
 */

// const { onOpen, isOpen, onClose } = useDisclosure();

const CommunityList = ({ communities }: CommunityListProps): JSX.Element => {
  const communityList = communities.map((community: Community, i: number) => {
    return (
      <CommunityCard key={i} community={community} />
    );
  });

  return (
    <div className="mt-10 mx-11">
      <p className="text-purple-softpurple mb-3 font-librefranklin font-semibold">My Communities</p>
      {communityList}
      
      <button className="text-blue-darkblue font-librefranklin text-md border border-gray-lightgray py-1 px-6 rounded-sm mt-5 transition ease-in-out delay-100 hover:bg-gray-200 duration-150"><span className="text-lg">+</span> Add</button>
      {/* <ModalTemplate /> */}
    </div>
  );
};

export default CommunityList;
