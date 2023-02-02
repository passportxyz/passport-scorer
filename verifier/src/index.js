const express = require("express");

const app = express();

import("dids").then((dids) => {
  import("@didtools/cacao").then((didtools) => {
    import("multiformats/cid").then((multiformats) => {
      import("key-did-resolver").then((KeyResolver) => {
        const DID = dids.DID;
        const Cacao = didtools.Cacao;
        const CID = multiformats.CID;

        app.post("/verify", (req, res) => {
          const jws_restored = {
            signatures: req.body.signature,
            payload: req.body.payload,
            cid: CID.decode(new Uint8Array(req.body.cid)),
          };

          Cacao.fromBlockBytes(new Uint8Array(req.body.cacao)).then((cacao) => {
            const did = new DID({
              resolver: KeyResolver.getResolver(),
            });
            did
              .verifyJWS(jws_restored, {
                issuer: req.body.issuer,
                capability: cacao,
                disableTimecheck: true,
              })
              .then((verifyResult) => {
                console.log("Verification ok!");
                res.json({ status: "ok" });
              })
              .catch((error) => {
                res.status(400);
                console.error("Verification failed:", error);
                res.json({ status: "failed", error: error.toString() });
              });
          });
        });
      });
    });
  });
});

// parse JSON post bodys
app.use(express.json());

// set cors to accept calls from anywhere
app.use(cors());

// default port to listen on
const port = process.env.IAM_PORT || 80;

app.listen(port, () => {
  // eslint-disable-next-line no-console
  console.log(`server started at http://localhost:${port}`);
});
