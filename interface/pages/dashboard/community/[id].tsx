import { useEffect, useState } from "react";

// Next
import { useRouter } from "next/router";

// Components
import { Layout } from "../../../components/Layout";
import { Radio, RadioGroup } from "@chakra-ui/react";

// Requests
import {
  getCommunityScorers,
  Scorer,
  updateCommunityScorers,
} from "../../../utils/account-requests";

const defaultScorer = {
  name: "Gitcoin Scoring",
  description:
    "Stamps and data are binarily verified, aggregated, and scored relative to all other attestations.",
  id: "gitcoin",
};

const defaultScorers = [defaultScorer];

const Community = () => {
  const [activeScorer, setActiveScorer] = useState("gitcoin");

  // TODO: Uncomment once scorer configuration is further fleshed out
  // const router = useRouter();
  // const [scorers, setScorers] = useState<Scorer[]>([]);

  // const { id } = router.query;

  // const updateScorer = async (communityId: string, scorerId: string) => {
  //   await updateCommunityScorers(communityId, scorerId);
  //   const communityScorers = await getCommunityScorers(id as string);
  //   setActiveScorer(communityScorers.currentScorer || "");
  // };

  // useEffect(() => {
  //   const getScorers = async () => {
  //     if (!id) {
  //       setScorers([]);
  //       return;
  //     }
  //     const communityScorers = await getCommunityScorers(id as string);

  //     setScorers(communityScorers.scorers);
  //     setActiveScorer(communityScorers.currentScorer || "");
  //   };
  //   getScorers();
  // }, [id]);

  return (
    <Layout>
      {defaultScorers.map((scorer) => (
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
              // onChange={() => updateScorer(id as string, scorer.id)}
            >
              <p className="mb-2 font-librefranklin font-semibold text-blue-darkblue">
                {scorer.name}
              </p>
              <p className="font-librefranklin text-purple-softpurple">
                {scorer.description}
              </p>
            </Radio>
          </RadioGroup>
        </div>
      ))}
    </Layout>
  );
};

export default Community;
