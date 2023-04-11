// Next.js API route support: https://nextjs.org/docs/api-routes/introduction
require("dotenv").config();
const sqlite3 = require("sqlite3");
const { open } = require("sqlite");

export default async function handler(req, res) {
  const db = await open({
    filename: "airdrop.db",
    driver: sqlite3.Database,
  });
  const rows = await db.all("SELECT * FROM airdrop_addresses");
  await db.close();
  res.status(200).json(rows);
}
