import { useState, useEffect } from "react";
import axios from "axios";
import { useSignMessage, useEnsName } from "wagmi";
import { verifyMessage } from "ethers/lib/utils";
import { useAccount } from "wagmi";
import styles from "@/styles/Score.module.css";

export default function Score() {
  useEffect(() => {
    setIsMounted(true);
  }, []);

  const { address } = useAccount({
    onDisconnect() {
      setNonce("");
      setPassportScore(0);
    },
  });

  const { data, isError, isLoading } = useEnsName({
    address: address,
  });

  useEffect(() => {
    setNonce("");
    setPassportScore(0);
    async function fetchPassportScore() {
      //  Step #1 (Optional, only required if using the "signature" param when submitting a user's passport. See https://docs.passport.gitcoin.co/building-with-passport/scorer-api/endpoint-definition#submit-passport)
      //    We call our /api/scorer-message endpoint (/pages/api/scorer-message.js) which internally calls /registry/signing-message
      //    on the scorer API. Instead of calling /registry/signing-message directly, we call it via our api endpoint so we do not
      //    expose our scorer API key to the frontend.
      //    This will return a response like:
      //    {
      //      message: "I hereby agree to submit my address in order to score my associated Gitcoin Passport from Ceramic.",
      //      nonce: "b7e3b0f86820744b9242dd99ce91465f10c961d98aa9b3f417f966186551"
      //    }
      const scorerMessageResponse = await axios.get("/api/scorer-message");
      setNonce(scorerMessageResponse.data.nonce);

      //  Step #2 (Optional, only required if using the "signature" param when submitting a user's passport.)
      //    Have the user sign the message that was returned from the scorer api in Step #1.
      signMessage({ message: scorerMessageResponse.data.message });
    }
    fetchPassportScore();
  }, [address]);

  const { signMessage } = useSignMessage({
    async onSuccess(data, variables) {
      // Verify signature when sign message succeeds
      const address = verifyMessage(variables.message, data);

      //  Step #3
      //    Now that we have the signature from the user, we can submit their passport for scoring
      //    We call our /api/submit-passport endpoint (/pages/api/submit-passport.js) which
      //    internally calls /registry/submit-passport on the scorer API.
      //    This will return a response like:
      //    {
      //      address: "0xabc",
      //      error: null,
      //      evidence: null,
      //      last_score_timestamp: "2023-03-26T15:17:03.393567+00:00",
      //      score: null,
      //      status: "PROCESSING"
      //    }
      const submitResponse = await axios.post("/api/submit-passport", {
        address: address, // Required: The user's address you'd like to score.
        community: process.env.NEXT_PUBLIC_SCORER_ID, // Required: get this from one of your scorers in the Scorer API dashboard https://scorer.gitcoin.co/
        signature: data, // Optional: The signature of the message returned in step #1
        nonce: nonce, // Optional: The nonce returned in Step #1
      });

      //  Step #4
      //    Finally we can submit the user's address for scoring.
      //    We call our /api/score/{scorer_id}/{address} endpoint (/pages/api/score/[scorer_id]/[address].js) which internally calls
      //    /registry/score/{communityId}/{address}
      //    This will return a response like:
      //    {
      //      address: "0xabc",
      //      error: null,
      //      evidence: null,
      //      last_score_timestamp: "2023-03-26T15:17:03.393567+00:00",
      //      score: "1.574606692",
      //      status: ""DONE""
      //    }
      const scoreResponse = await axios.get(
        `/api/score/${process.env.NEXT_PUBLIC_SCORER_ID}/${address}`
      );

      // Make sure to check the status
      if (
        scoreResponse.data.status === "ERROR" ||
        scoreResponse.data.error !== null
      ) {
        setPassportScore(0);
        alert(scoreResponse.data.error);
        return;
      }

      // Store the user's passport score for later use.
      setPassportScore(scoreResponse.data.score || 0);
    },
  });

  // This isMounted check is needed to prevent hydration errors with next.js server side rendering.
  // See https://github.com/wagmi-dev/wagmi/issues/542 for more details.
  const [isMounted, setIsMounted] = useState(false);
  const [nonce, setNonce] = useState("");
  const [passportScore, setPassportScore] = useState(0);

  function abbreviateAddress(ethAddress) {
    if (!ethAddress || ethAddress.length < 10) {
      throw new Error("Invalid Ethereum address");
    }

    const prefix = ethAddress.slice(0, 6);
    const suffix = ethAddress.slice(-4);

    return `${prefix}...${suffix}`;
  }

  function renderContent() {
    if (isMounted && address) {
      return (
        <p>
          Welcome, {data || abbreviateAddress(address)} (
          <div className={styles.tooltip} style={{ color: "rgb(111 63 245)" }}>
            {passportScore}
            <span className={styles.tooltiptext}>
              This is your Gitcoin Passport Score
            </span>
          </div>
          )
        </p>
      );
    } else {
      return <p>Connect your wallet to see your score</p>;
    }
  }

  return <div>{renderContent()}</div>;
}
