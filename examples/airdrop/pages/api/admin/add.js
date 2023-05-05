import db from "../../../db";

export default async function handler(req, res) {
  const { address } = req.body;

  if (address === undefined || address === "") {
    res
      .status(400)
      .json({ successful: false, error: "Address cannot be empty" });
    return;
  }

  const initial = await db("airdrop_addresses").where({ address: address });
  if (initial.length !== 0) {
    res
      .status(400)
      .json({ successful: false, error: "Address is already on airdrop list" });
    return;
  }
  const rows = await db("airdrop_addresses")
    .insert({ address: address, score: 0 })
    .returning("*");

  res.status(200).json({
    successful: true,
    added: { id: rows[0].id, address: address, score: 0 },
  });
}
