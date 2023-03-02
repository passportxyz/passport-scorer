// --- React components/methods
import React from "react";

// --- Types
import { Community } from "../utils/account-requests";

// Components
import { Icon } from "@chakra-ui/icons";

// --- Next
import { useRouter } from "next/router";

// -- Other
import { useCaseByName } from "./UseCaseModal";

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

  const useCaseByNamee = useCaseByName;
  const useCase = useCaseByName.get(community.use_case);
  const useCaseIcon = useCase ? (
    <Icon boxSize={19.5}>{useCase.icon("#6F3FF5")}</Icon>
  ) : null;
  return (
    <div className="flex items-center px-4 py-4 sm:px-6">
      <div className="min-w-0 flex-1 md:grid md:grid-cols-3 md:gap-4">
        <div>
          <p className="my-2 text-sm text-purple-gitcoinpurple">
            {useCaseIcon}
            {community.use_case}
          </p>
          <p className="truncate text-base font-medium text-purple-darkpurple">{community.name}</p>
          <p className="mt-2 flex items-center text-sm text-purple-softpurple">
            <span className="truncate">{community.description}</span>
          </p>
        </div>
        <div className="pt-5">
          <p className="mt-2 flex flex-row-reverse text-sm text-purple-softpurple">
            Created:
          </p>
          <p className="flex flex-row-reverse text-sm text-purple-softpurple">
            {community.created_at?new Date(community.created_at).toDateString():"unknown"}
          </p>
        </div>
        <div className="pt-5">
          <p className="mt-2 flex flex-row-reverse text-sm text-purple-softpurple">
            Scorer ID:
          </p>
          <p className="flex flex-row-reverse text-sm text-purple-softpurple">
            {community.id}
          </p>
        </div>
      </div>
    </div>
  );
};

export default CommunityCard;
