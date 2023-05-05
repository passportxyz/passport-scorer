// Next.js API route support: https://nextjs.org/docs/api-routes/introduction
const merkle = require("merkle");
const CryptoJS = require("crypto-js");
import db from "../../../db";

export default async function handler(req, res) {
  const rows = await db.select("*").from("airdrop_addresses");

  const addresses = rows.map((r) => r.address);
  const merkleRoot = calculateMerkleRoot(addresses);

  res.status(200).json(merkleRoot);
}

function calculateMerkleRoot(addresses) {
  // Hash the addresses using the SHA-256 algorithm
  const hashedAddresses = addresses.map((address) =>
    CryptoJS.SHA256(address).toString(CryptoJS.enc.Hex)
  );

  // Create a Merkle tree with the hashed addresses
  const tree = merkle("sha256").sync(hashedAddresses);

  // Return the Merkle root
  return tree.root();
}
