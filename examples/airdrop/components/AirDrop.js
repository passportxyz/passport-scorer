import { useState, useEffect } from "react";
import axios from "axios";
import { verifyMessage } from "ethers/lib/utils";
import { useAccount, useSignMessage } from "wagmi";

export default function AirDrop() {
  useEffect(() => {
    setIsMounted(true);
  }, []);

  const { address } = useAccount({
    onDisconnect() {
      reset();
    },
  });

  useEffect(() => {
    reset();
    // Query the airdrop_addresses table to check if this user is already in the aidrop list.
    // If they are there is no need to connect to the scorer API, we can display their passport score immediately.
    async function checkIfAddressAlreadyInAirdropList() {
      const resp = await axios.post(`/api/airdrop/check/${address}`);
      if (resp.data && resp.data.address) {
        setChecked(true);
        setPassportScore(resp.data.score);
      }
    }
    checkIfAddressAlreadyInAirdropList();
  }, [address]);

  async function addToAirdrop() {
    setNonce("");
    setPassportScore(0);
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
    console.log("scorerMessageResponse: ", scorerMessageResponse);
    if (scorerMessageResponse.status !== 200) {
      console.error("failed to fetch scorer message");
      return;
    }
    setNonce(scorerMessageResponse.data.nonce);

    //  Step #2 (Optional, only required if using the "signature" param when submitting a user's passport.)
    //    Have the user sign the message that was returned from the scorer api in Step #1.
    signMessage({ message: scorerMessageResponse.data.message });
  }

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
        signature: data, // Optional: The signature of the message returned in Step #1
        nonce: nonce, // Optional: The nonce returned in Step #1
      });
      console.log("submitResponse: ", submitResponse);

      //  Step #4
      //    Finally, we can attempt to add the user to the airdrop list.
      //    We call our /api/airdrop/{scorer_id}/{address} endpoint (/pages/api/airdrop/[scorer_id]/[address].js) which internally calls
      //    /registry/score/{scorer_id}/{address}
      //    This will return a response like:
      //    {
      //      address: "0xabc",
      //      error: null,
      //      evidence: null,
      //      last_score_timestamp: "2023-03-26T15:17:03.393567+00:00",
      //      score: "1.574606692",
      //      status: ""DONE""
      //    }
      //    We check if the returned score is above our threshold to qualify for the airdrop.
      //    If the score is above our threshold, we add the user to the airdrop list.
      const scoreResponse = await axios.get(
        `/api/airdrop/add/${process.env.NEXT_PUBLIC_SCORER_ID}/${address}`
      );
      console.log("scoreResponse: ", scoreResponse.data);

      // Make sure to check the status
      if (scoreResponse.data.status === "ERROR") {
        setPassportScore(0);
        alert(scoreResponse.data.error);
        return;
      }

      // Store the user's passport score for later use.
      setPassportScore(scoreResponse.data.score);
      setChecked(true);

      if (scoreResponse.data.score < 1) {
        alert("Sorry, you're not eligible for the airdrop.");
      } else {
        alert("You're eligible for the airdrop! Your address has been added.");
      }
    },
  });

  function reset() {
    setNonce("");
    setPassportScore(0);
    setChecked(false);
  }

  // This isMounted check is needed to prevent hydration errors with next.js server side rendering.
  // See https://github.com/wagmi-dev/wagmi/issues/542 for more details.
  const [isMounted, setIsMounted] = useState(false);
  const [nonce, setNonce] = useState("");
  const [passportScore, setPassportScore] = useState(0);
  const [checked, setChecked] = useState(false);

  function display() {
    if (isMounted && address) {
      if (checked) {
        if (passportScore < 1) {
          return (
            <div>
              <p>
                Your score isn't high enough, collect more stamps to qualify.
              </p>
              <p>
                passport score:{" "}
                <span style={{ color: "rgb(111 63 245" }}>
                  {passportScore | 0}
                </span>
              </p>
              <p>minimum needed: 1</p>
            </div>
          );
        } else {
          return (
            <div>
              <h3>You've been added to the airdrop!</h3>
              <p>
                passport score:{" "}
                <span style={{ color: "rgb(111 63 245" }}>{passportScore}</span>
              </p>
            </div>
          );
        }
      } else {
        return (
          <button
            style={{
              padding: "20px 30px",
              backgroundColor: "rgb(111 63 245)",
              border: "none",
              color: "white",
              cursor: "pointer",
              fontWeight: "bold",
            }}
            onClick={() => addToAirdrop(address)}
          >
            Add address to airdrop
          </button>
        );
      }
    } else {
      return (
        <p>
          Connect your wallet to find out if you're eligible for the airdrop.
        </p>
      );
    }
  }

  return <div>{display()}</div>;
}
