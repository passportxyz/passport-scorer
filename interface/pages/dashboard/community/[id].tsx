import { useState } from "react";

// Next
import { useRouter } from "next/router";

// Components
import { Layout } from "../../../components/Layout";
import { Radio, RadioGroup } from "@chakra-ui/react";

const defaultScorer = {
  name: "Gitcoin Scoring",
  description:
    "Stamps and data are binarily verified, aggregated, and scored relative to all other attestations.",
  scorerType: "gitcoin",
};

const Community = () => {
  const [value, setValue] = useState("gitcoin");
  const router = useRouter();
  const { id } = router.query;

  return (
    <Layout>
      <div className="flex w-full justify-start border-x border-t border-gray-lightgray bg-white p-4 first-of-type:rounded-t-md last-of-type:rounded-b-md last-of-type:border-b hover:bg-gray-50">
        {/* first column */}
        <RadioGroup className="mt-4" onChange={setValue} value={value}>
          <Radio
            colorScheme={"purple"}
            value={defaultScorer.scorerType}
            className="mr-4"
          />
        </RadioGroup>
        <div className="grid-rows grid">
          <p className="mb-2 font-librefranklin font-semibold text-blue-darkblue">
            {defaultScorer.name}
          </p>
          <p className="font-librefranklin text-purple-softpurple">
            {defaultScorer.description}
          </p>
        </div>
      </div>
    </Layout>
  );
};

export default Community;
