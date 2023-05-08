// Next.js API route support: https://nextjs.org/docs/api-routes/introduction
const formidable = require("formidable");
const fs = require("fs");
import db from "../../../db";

export const config = {
  api: {
    bodyParser: false,
  },
};

const handler = async (req, res) => {
  if (req.method === "POST") {
    try {
      const data = await parseForm(req);

      // Save the file to your preferred location, e.g., a local folder or cloud storage.
      // You can also save the name and description to a database.
      const { file, fields } = data;
      const { name, description } = fields;

      console.log("file: ", file);

      // Perform other tasks, like saving data to the database or calling other APIs.
      await db("theme").insert({
        name: name,
        description: description,
        image: file.data,
      });

      res.status(200).json({
        success: true,
        message: "File uploaded successfully",
        data: { name, description, filename: file.name },
      });
    } catch (error) {
      console.log(error);
      res
        .status(500)
        .json({ success: false, message: "File upload failed", error });
    }
  } else {
    res.status(405).json({ success: false, message: "Method not allowed" });
  }
};

const parseForm = (req) => {
  return new Promise((resolve, reject) => {
    const form = new formidable.IncomingForm();

    form.parse(req, (err, fields, files) => {
      if (err) {
        reject(err);
        return;
      }

      if (files.file) {
        const fileData = fs.readFileSync(files.file.filepath);

        const file = {
          name: files.file.name,
          type: files.file.type,
          data: fileData,
        };

        resolve({ fields, file });
      } else {
        reject(new Error("No file provided"));
      }
    });
  });
};

export default handler;
