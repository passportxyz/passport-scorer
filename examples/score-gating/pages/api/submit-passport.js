const axios = require("axios");
require("dotenv").config();

export default async function handler(req, res) {
  const { address, community, signature, nonce } = req.body;
  const data = await submitPassport(address, community, signature, nonce);
  res.status(200).json(data);
}

async function submitPassport(address, community, signature, nonce) {
  const axiosSubmitPassportConfig = {
    headers: {
      "X-API-KEY": process.env.SCORER_API_KEY,
      Accept: "application/json",
      "Content-Type": "application/json",
    },
  };

  const axiosSubmitPassportData = {
    address,
    community,
    signature,
    nonce,
  };
  const { data } = await axios.post(
    "https://api.scorer.gitcoin.co/registry/submit-passport",
    axiosSubmitPassportData,
    axiosSubmitPassportConfig
  );
  return data;
}
