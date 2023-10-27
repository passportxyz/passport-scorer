const crypto = require("crypto");
const { Wallet } = require("ethers");
const express = require("express");

// simple express server
// one endpoint to generate a private key and address
// another endpoint that accepts a private key and message and returns a signature

const app = express();
app.use(express.json());

app.get("/generate", (_req, res) => {
  const id = crypto.randomBytes(32).toString("hex");
  const privateKey = "0x" + id;
  const wallet = new Wallet(privateKey);
  const address = wallet.address;
  res.json({
    privateKey,
    address,
  });
});

app.post("/sign", (req, res) => {
  const { privateKey, message } = req.body;
  const wallet = new Wallet(privateKey);
  wallet.signMessage(message).then((signature) => {
    res.json({ signature: signature.toString() });
  });
});

const port = 8123;
app.listen(port, () => {
  console.log(`Server listening on port ${port}`);
});
