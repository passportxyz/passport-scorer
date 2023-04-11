const axios = require("axios");
const sqlite3 = require("sqlite3");
const { open } = require("sqlite");
require("dotenv").config();

export default async function handler(req, res) {
  const { address, scorer_id: scorerId } = req.query;
  const data = await fetchScore(address, scorerId);

  if (data.score > 1) {
    const db = await open({
      filename: "airdrop.db",
      driver: sqlite3.Database,
    });
    await db.run(
      "INSERT INTO airdrop_addresses (address, score) VALUES (?, ?)",
      [address, data.score]
    );
    await db.close();
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
