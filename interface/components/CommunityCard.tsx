// --- React components/methods
import React from "react";

// --- Types
import { Community } from "../pages/dashboard";

type CommunityCardProps = {
  community: Community;
}

const CommunityCard = ({ community }: CommunityCardProps): JSX.Element => {
  return (
    <div className="border-gray-lightgray border-x border-t last-of-type:border-b p-4 first-of-type:rounded-t-md last-of-type:rounded-b-md bg-white">
      <p className="font-librefranklin font-semibold text-blue-darkblue mb-2">{community.name}</p>
      <p className="font-librefranklin text-purple-softpurple">{community.description}</p>
    </div>
  );
};

export default CommunityCard;