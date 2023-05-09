import db from "../../../../db";

export default async function handler(req, res) {
  const { address } = req.query;
  const rows = await db("airdrop_addresses").where({ address: address });

  res.status(200).json(rows[0]);
}
