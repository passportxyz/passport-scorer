import { useEffect, useState } from "react";

// Next
import { useRouter } from "next/router";

// Components
import { RadioGroup, Radio } from "../ui/Radio";

// Requests
import {
  getCommunityScorers,
  Scorer,
  updateCommunityScorers,
} from "../utils/account-requests";

const defaultScorer = {
  name: "Human Scoring",
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
    <RadioGroup
      value={activeScorer}
      onChange={setActiveScorer}
      className="gap-0"
    >
      {scorers.map((scorer) => (
        <div
          key={scorer.id}
          className="flex w-full justify-start border-x border-t border-gray-lightgray bg-white p-4 first-of-type:rounded-t-md last-of-type:rounded-b-md last-of-type:border-b hover:bg-gray-50"
        >
          <Radio
            data-testid={`radio-${scorer.id}`}
            value={scorer.id}
            className="mr-4"
            onChange={() => updateScorer(id, scorer.id)}
          >
            <p className="mb-2 font-sans font-semibold text-foreground">
              {scorer.label}
            </p>
          </Radio>
        </div>
      ))}
    </RadioGroup>
  );
};

export default Community;
