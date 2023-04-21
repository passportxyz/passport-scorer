// Next.js API route support: https://nextjs.org/docs/api-routes/introduction
require("dotenv").config();
const sqlite3 = require("sqlite3");
const { open } = require("sqlite");

export default async function handler(req, res) {
  const db = await open({
    filename: "airdrop.db",
    driver: sqlite3.Database,
  });
  await db.run(
    "DELETE FROM airdrop_addresses WHERE address = ?",
    req.body.address
  );

  await db.close();
  res.status(200).json({ success: true });
}
