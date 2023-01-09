// --- React components/methods
import React from "react";

// --- Types
import { Community } from "../utils/account-requests";

// Components
import { DeleteIcon, EditIcon } from "@chakra-ui/icons";

// --- Next
import { useRouter } from "next/router";

type CommunityCardProps = {
  setUpdatedCommunityName: Function;
  setUpdatedCommunityDescription: Function;
  setUpdatedCommunityId: Function;
  community: Community;
  communityId: Community["id"];
  handleDeleteCommunity: Function;
  setUpdateCommunityModalOpen: Function;
};

const CommunityCard = ({
  community,
  handleDeleteCommunity,
  communityId,
  setUpdateCommunityModalOpen,
  setUpdatedCommunityName,
  setUpdatedCommunityDescription,
  setUpdatedCommunityId,
}: CommunityCardProps): JSX.Element => {
  const router = useRouter();

  return (
    <div className="grid w-full auto-cols-auto grid-cols-2 items-center justify-between border-x border-t border-gray-lightgray bg-white p-4 first-of-type:rounded-t-md last-of-type:rounded-b-md last-of-type:border-b hover:bg-gray-50">
      {/* first column */}
      <div className="grid-rows grid">
        <p id="community-name" className="mb-2 cursor-pointer font-librefranklin font-semibold text-blue-darkblue">
          <a
            onClick={() => router.push(`/dashboard/community/${community.id}`)}
          >
            {community.name}
          </a>
        </p>
        <p id="community-description" className="font-librefranklin text-purple-softpurple">
          {community.description}
        </p>
      </div>
      {/* second column */}
      <div className="grid grid-cols-2 justify-self-end">
        <button
          data-testid="edit-community-button"
          className="mr-2 justify-self-end rounded-md border border-gray-lightgray bg-white px-3 pt-1 pb-2 shadow-sm shadow-gray-100"
          onClick={async () => {
            setUpdatedCommunityId(community.id);
            setUpdatedCommunityName(community.name);
            setUpdatedCommunityDescription(community.description);
            setUpdateCommunityModalOpen(true);
          }}
        >
          <EditIcon color="#757087" />
        </button>
        <button
          data-testid="delete-community-button"
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
