const axios = require("axios");
require("dotenv").config();

export default async function handler(req, res) {
  const { address, scorer_id: scorerId } = req.query;
  const data = await fetchScore(address, scorerId);
  res.status(200).json(data);
}

async function fetchScore(address, scorerId) {
  const axiosGetScoreConfig = {
    headers: {
      "X-API-KEY": process.env.SCORER_API_KEY,
      Accept: "application/json",
      "Content-Type": "application/json",
    },
  };
  const { data } = await axios.get(
    `https://api.scorer.gitcoin.co/registry/score/${scorerId}/${address}`,
    axiosGetScoreConfig
  );

  return data;
}
