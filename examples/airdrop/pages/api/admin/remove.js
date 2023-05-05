// Next.js API route support: https://nextjs.org/docs/api-routes/introduction
import db from "../../../db";

export default async function handler(req, res) {
  await db("airdrop_addresses").where({ address: req.body.address }).del();

  res.status(200).json({ success: true });
}
