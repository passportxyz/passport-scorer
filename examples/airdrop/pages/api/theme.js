// Next.js API route support: https://nextjs.org/docs/api-routes/introduction
import db from "../../db";

export default async function handler(req, res) {
  const theme = await db("theme").orderBy("id", "desc").limit(1);
  if (theme.length === 0) {
    return res.status(200).json({ status: "success", theme: null });
  }

  const base64data = new Buffer(theme[0].image).toString("base64");
  res
    .status(200)
    .json({ status: "success", theme: { ...theme[0], image: base64data } });
}
