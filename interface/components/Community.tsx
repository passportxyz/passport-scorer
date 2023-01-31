import { useEffect, useState } from "react";

// Next
import { useRouter } from "next/router";

// Components
import { Radio, RadioGroup } from "@chakra-ui/react";

// Requests
import {
  getCommunityScorers,
  Scorer,
  updateCommunityScorers,
} from "../utils/account-requests";

const defaultScorer = {
  name: "Gitcoin Scoring",
  description:
    "Stamps and data are binarily verified, aggregated, and scored relative to all other attestations.",
  id: "gitcoin",
};

const defaultScorers = [defaultScorer];

const Community = ({ id }: { id: string }) => {
  const [activeScorer, setActiveScorer] = useState("gitcoin");

  const router = useRouter();
  const [scorers, setScorers] = useState<Scorer[]>([]);

  const updateScorer = async (communityId: string, scorerId: string) => {
    await updateCommunityScorers(communityId, scorerId);
    const communityScorers = await getCommunityScorers(id);
    setActiveScorer(communityScorers.currentScorer || "");
  };

  useEffect(() => {
    const getScorers = async () => {
      if (!id) {
        setScorers([]);
        return;
      }
      const communityScorers = await getCommunityScorers(id);

      setScorers(communityScorers.scorers);
      setActiveScorer(communityScorers.currentScorer || "");
    };
    getScorers();
  }, [id]);

  return (
    <>
      {scorers.map((scorer) => (
        <div
          key={scorer.id}
          className="flex w-full justify-start border-x border-t border-gray-lightgray bg-white p-4 first-of-type:rounded-t-md last-of-type:rounded-b-md last-of-type:border-b hover:bg-gray-50"
        >
          {/* first column */}
          <RadioGroup
            className="mt-4"
            onChange={setActiveScorer}
            value={activeScorer}
          >
            <Radio
              data-testid={`radio-${scorer.id}`}
              colorScheme={"purple"}
              value={scorer.id}
              className="mr-4"
              onChange={() => updateScorer(id, scorer.id)}
            >
              <p className="mb-2 font-librefranklin font-semibold text-blue-darkblue">
                {scorer.label}
              </p>
              {/* <p className="font-librefranklin text-purple-softpurple">
              {scorer.description}
            </p> */}
            </Radio>
          </RadioGroup>
        </div>
      ))}
    </>
  );
};

export default Community;
