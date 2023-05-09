// Next.js API route support: https://nextjs.org/docs/api-routes/introduction
import db from "../../../db";

export default async function handler(req, res) {
  const rows = await db.select("*").from("airdrop_addresses");
  res.status(200).json(rows);
}
