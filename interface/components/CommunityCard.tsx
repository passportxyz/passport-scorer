// --- React components/methods
import React from "react";

// --- Types
import { Community } from "../utils/account-requests";

// Components
import { DeleteIcon, EditIcon } from "@chakra-ui/icons";

// --- Next
import { useRouter } from "next/router";

type CommunityCardProps = {
  setUpdatedScorerName: Function;
  setUpdatedScorerDescription: Function;
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
  setUpdatedScorerName,
  setUpdatedScorerDescription,
  setUpdatedCommunityId,
}: CommunityCardProps): JSX.Element => {
  const router = useRouter();

  return (
    <div className="flex items-center px-4 py-4 sm:px-6">
      <div className="min-w-0 flex-1 px-4 md:grid md:grid-cols-3 md:gap-4">
        <div>
          <p className="truncate text-base font-medium">{community.name}</p>
          <p className="mt-2 flex items-center text-sm text-gray-500">
            <span className="truncate">{community.description}</span>
          </p>
        </div>
        <div className="text-right">
          <p className="mt-2 flex flex-row-reverse text-sm text-gray-500">
            Created:
          </p>
          <p className="flex flex-row-reverse text-sm text-gray-500">
            {new Date(community.created_at).toDateString()}
          </p>
        </div>
        <div>
          <p className="mt-2 flex flex-row-reverse text-right text-sm text-gray-500">
            Scorer ID:
          </p>
          <p className="flex flex-row-reverse text-sm text-gray-500">
            {community.id}
          </p>
        </div>
      </div>
    </div>
  );
};

export default CommunityCard;
