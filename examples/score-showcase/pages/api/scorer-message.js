// Next.js API route support: https://nextjs.org/docs/api-routes/introduction
const axios = require("axios");
require("dotenv").config();

export default async function handler(req, res) {
  // This endpoint will call /registry/signing-message and return the message that needs to be signed by the user
  //  as well as the nonce that should be submitted to /registry/submit-passport
  const messageAndNonce = await fetchMessageAndNonce();
  res.status(200).json(messageAndNonce);
}

async function fetchMessageAndNonce() {
  const axiosSigningMessageConfig = {
    headers: {
      "X-API-KEY": process.env.SCORER_API_KEY,
      Accept: "application/json",
      "Content-Type": "application/json",
    },
  };
  const { data } = await axios.get(
    "https://api.scorer.gitcoin.co/registry/signing-message",
    axiosSigningMessageConfig
  );
  return data;
}
