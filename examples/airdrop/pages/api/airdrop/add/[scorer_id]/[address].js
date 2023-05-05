const axios = require("axios");
import db from "../../../../../db";

export default async function handler(req, res) {
  const { address, scorer_id: scorerId } = req.query;
  const data = await fetchScore(address, scorerId);

  if (data.score > 1) {
    await db("airdrop_addresses").insert({
      address: address,
      score: data.score,
    });
  }
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
