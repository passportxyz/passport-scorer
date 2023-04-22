const sqlite3 = require("sqlite3");
const { open } = require("sqlite");
require("dotenv").config();

export default async function handler(req, res) {
  const { address } = req.body;

  if (address === undefined || address === "") {
    res
      .status(400)
      .json({ successful: false, error: "Address cannot be empty" });
    return;
  }

  const db = await open({
    filename: "airdrop.db",
    driver: sqlite3.Database,
  });
  const initial = await db.get(
    "SELECT * FROM airdrop_addresses WHERE address = ?",
    [address]
  );
  if (initial !== undefined) {
    res
      .status(400)
      .json({ successful: false, error: "Address is already on airdrop list" });
    return;
  }
  await db.run("INSERT INTO airdrop_addresses (address, score) VALUES (?, ?)", [
    address,
    0,
  ]);
  const row = await db.get(
    "SELECT * FROM airdrop_addresses WHERE address = ?",
    [address]
  );
  await db.close();

  res.status(200).json({
    successful: true,
    added: { id: row.id, address: address, score: 0 },
  });
}
