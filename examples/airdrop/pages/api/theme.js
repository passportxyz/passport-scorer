// Next.js API route support: https://nextjs.org/docs/api-routes/introduction
const sqlite3 = require("sqlite3");
const { open } = require("sqlite");

export default async function handler(req, res) {
  const db = await open({
    filename: "airdrop.db",
    driver: sqlite3.Database,
  });
  const row = await db.get("SELECT * FROM theme ORDER BY ID DESC LIMIT 1");
  const base64data = new Buffer(row.image).toString("base64");
  await db.close();
  res
    .status(200)
    .json({ status: "success", theme: { ...row, image: base64data } });
}
