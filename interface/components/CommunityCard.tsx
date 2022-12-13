// --- React components/methods
import React from "react";

// --- Types
import { Community } from "../utils/account-requests";

// Components
import { DeleteIcon, EditIcon } from "@chakra-ui/icons";

type CommunityCardProps = {
  setUpdatedCommunityName: Function;
  setUpdatedCommunityDescription: Function;
  setUpdatedCommunityId: Function;
  community: Community;
  communityId: Community["id"];
  handleDeleteCommunity: Function;
  setUpdateCommunityModalOpen: Function;
}

const CommunityCard = ({
  community,
  handleDeleteCommunity,
  communityId,
  setUpdateCommunityModalOpen,
  setUpdatedCommunityName,
  setUpdatedCommunityDescription,
  setUpdatedCommunityId,
}: CommunityCardProps): JSX.Element => {
  return (
    <div className="grid grid-cols-2 auto-cols-auto border-x border-t last-of-type:border-b first-of-type:rounded-t-md last-of-type:rounded-b-md w-full items-center justify-between border-gray-lightgray bg-white p-4 hover:bg-gray-50">
      {/* first column */}
      <div className="grid grid-rows">
        <p className="font-librefranklin font-semibold text-blue-darkblue mb-2"><a href="#">#{community.id} - {community.name}</a></p>
        <p className="font-librefranklin text-purple-softpurple">{community.description}</p>
      </div>
      {/* second column */}
      <div className="grid grid-cols-2 justify-self-end">
        <button
          data-testid="edit-community-button"
          className="mr-2 justify-self-end rounded-md border border-gray-lightgray bg-white px-3 pt-1 pb-2 shadow-sm shadow-gray-100"
          onClick={async () => {
            setUpdatedCommunityId(community.id)
            setUpdatedCommunityName(community.name);
            setUpdatedCommunityDescription(community.description);
            setUpdateCommunityModalOpen(true);
          }}
        >
          <EditIcon color="#757087" />
        </button>
        <button
          className="justify-self-end rounded-md border border-gray-lightgray bg-white px-3 pt-1 pb-2 shadow-sm shadow-gray-100"
          onClick={async () => await handleDeleteCommunity(communityId)}
        >
          <DeleteIcon color="#757087" />
        </button>
      </div>
    </div>
  );
};

export default CommunityCard;
