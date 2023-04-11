// Next.js API route support: https://nextjs.org/docs/api-routes/introduction
require("dotenv").config();
const sqlite3 = require("sqlite3");
const { open } = require("sqlite");
const merkle = require("merkle");
const CryptoJS = require("crypto-js");

export default async function handler(req, res) {
  const db = await open({
    filename: "airdrop.db",
    driver: sqlite3.Database,
  });
  const rows = await db.all("SELECT * FROM airdrop_addresses");

  const addresses = rows.map((r) => r.address);
  const merkleRoot = calculateMerkleRoot(addresses);

  await db.close();
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
