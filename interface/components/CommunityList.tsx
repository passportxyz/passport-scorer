// --- React components/methods
import React, { useEffect, useState, useCallback } from "react";

// --- Components
import CommunityCard from "./CommunityCard";
import NoValues from "./NoValues";

// --- Utils
import {
  getCommunities,
  updateCommunity,
  deleteCommunity,
  Community,
} from "../utils/account-requests";

import UseCaseModal from "./UseCaseModal";
import { useToast } from "../ui/Toast";
import { StarIcon } from "@heroicons/react/24/outline";
import { PlusIcon } from "@heroicons/react/24/solid";

const CommunityList = () => {
  const toast = useToast();
  const [selectUseCaseModalOpen, setSelectUseCaseModalOpen] = useState(false);
  const [error, setError] = useState<undefined | string>();
  const [communities, setCommunities] = useState<Community[]>([]);
  const [communityLoadingStatus, setCommunityLoadingStatus] =
    useState<string>("initial");

  const fetchCommunities = useCallback(async () => {
    try {
      setCommunityLoadingStatus("loading");
      const data = await getCommunities();
      setCommunities(Array.isArray(data) ? data : []);
      setCommunityLoadingStatus("done");
    } catch (exc) {
      const error = exc as { response: { status: number } };
      setCommunityLoadingStatus("error");
      setCommunities([]);
      setError("There was an error fetching your Communities.");
    }
  }, []);

  useEffect(() => {
    const scorerCreated = Boolean(localStorage.getItem("scorerCreated"));

    if (scorerCreated) {
      toast.success("Your Scorer has been created.");
      localStorage.removeItem("scorerCreated");
    }

    fetchCommunities();
  }, []);

  const handleUpdateCommunity = async (
    communityId: number,
    name: string,
    description: string
  ) => {
    await updateCommunity(communityId, { name, description });
    await fetchCommunities();
  };

  const handleDeleteCommunity = async (communityId: number) => {
    await deleteCommunity(communityId);
    await fetchCommunities();
  };

  const communityItems = communities.map((community: Community, i: number) => {
    return (
      <CommunityCard
        key={i}
        community={community}
        onCommunityDeleted={fetchCommunities}
        handleUpdateCommunity={handleUpdateCommunity}
        handleDeleteCommunity={handleDeleteCommunity}
      />
    );
  });

  const communityList = (
    <div className="overflow-hidden rounded-[12px] border border-gray-200 bg-white shadow-card">
      <ul role="list" className="divide-y divide-gray-100">
        {communityItems}
      </ul>
    </div>
  );

  return (
    <>
      {communities.length === 0 ? (
        <NoValues
          title="Create a Scorer"
          description="Select unique scoring mechanisms that align with your application's goals."
          addActionText="Scorer"
          addRequest={() => {
            setSelectUseCaseModalOpen(true);
          }}
          icon={<StarIcon className="w-6" />}
        />
      ) : (
        <div className="mt-t mx-0">
          {communityList}

          <div className="mt-5 flex flex-wrap">
            <button
              className={
                "flex rounded-[12px] bg-black px-4 py-2 align-middle text-white font-medium hover:bg-gray-800 transition-colors" +
                (communities.length >= 5
                  ? " cursor-not-allowed disabled:bg-gray-200 disabled:text-gray-400"
                  : "")
              }
              onClick={() => {
                setSelectUseCaseModalOpen(true);
              }}
              disabled={
                communityLoadingStatus !== "done" || communities.length >= 5
              }
            >
              <PlusIcon className="mr-2 inline w-6 self-center" />{" "}
              <span className="self-center">Scorer</span>
            </button>
            <p className="ml-5 self-center py-3 text-xs text-gray-500">
              The scorer limit is five.
            </p>
          </div>
          {error && <div>{error}</div>}
        </div>
      )}
      <UseCaseModal
        isOpen={selectUseCaseModalOpen}
        existingScorers={communities}
        onClose={() => setSelectUseCaseModalOpen(false)}
      />
    </>
  );
};

export default CommunityList;
