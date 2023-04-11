const axios = require("axios");
const sqlite3 = require("sqlite3");
const { open } = require("sqlite");
require("dotenv").config();

export default async function handler(req, res) {
  const { address } = req.query;
  const db = await open({
    filename: "airdrop.db",
    driver: sqlite3.Database,
  });
  const row = await db.get(
    "SELECT * FROM airdrop_addresses WHERE address = ?",
    [address]
  );
  await db.close();

  res.status(200).json(row);
}
